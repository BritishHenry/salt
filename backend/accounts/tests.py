import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from accounts.models import ApiToken, User
from payments.models import Seller
from payments.stripe_api import StripeCallError, create_recipient_account
from services.browser_use.models import Profile, ProfilePage


ONBOARDING_URL = "https://stripe.test/onboard"
PASSWORD = "b3tt3r-pass-phrase"


class FakeBrowser:
    def __init__(self, profiles=None):
        self.profiles = list(profiles or [])
        self.created = []
        self.listed = []

    def list_profiles(self, query=None, page_size=None, page_number=None):
        self.listed.append(query)
        items = tuple(profile for profile in self.profiles if profile.user_id == query)
        return ProfilePage(
            items=items,
            total_items=len(items),
            page_number=1,
            page_size=10,
        )

    def create_profile(self, name=None, user_id=None):
        profile = Profile(
            id=f"prof_{len(self.created) + 1}",
            created_at="t",
            updated_at="t",
            user_id=user_id,
            name=name,
        )
        self.created.append(profile)
        self.profiles.append(profile)
        return profile


class AccountApiTests(TestCase):
    def setUp(self):
        self.browser = FakeBrowser()
        self.create_account = patch(
            "payments.services.create_recipient_account",
            return_value=("acct_123", "pending"),
        ).start()
        self.onboarding_link = patch(
            "payments.services.onboarding_link", return_value=ONBOARDING_URL
        ).start()
        patch(
            "accounts.services.onboarding_link", return_value=ONBOARDING_URL
        ).start()
        patch("accounts.services.BrowserUseClient", return_value=self.browser).start()
        self.addCleanup(patch.stopall)

    def signup(self, **overrides):
        body = {
            "email": "Ada@Example.com",
            "password": PASSWORD,
            "display_name": "Ada",
        }
        body.update(overrides)
        return self.client.post(
            "/api/accounts/signup/",
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_signup_creates_user_token_stripe_recipient_and_profile(self):
        response = self.signup()

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        user = User.objects.get(email="ada@example.com")
        token = ApiToken.objects.get(user=user)
        seller = Seller.objects.get(user=user)
        self.assertEqual(payload["token"], token.key)
        self.assertEqual(payload["user"]["id"], user.pk)
        self.assertEqual(payload["user"]["display_name"], "Ada")
        self.assertEqual(payload["stripe"]["seller_id"], seller.pk)
        self.assertEqual(payload["stripe"]["stripe_account_id"], "acct_123")
        self.assertEqual(payload["stripe"]["transfers_status"], "pending")
        self.assertEqual(payload["stripe"]["onboarding_url"], ONBOARDING_URL)
        self.assertEqual(payload["browser_profile"]["status"], "ready")
        self.assertEqual(payload["browser_profile"]["profile_id"], "prof_1")
        self.assertEqual(self.browser.created[0].user_id, str(user.pk))
        self.create_account.assert_called_once()

    def test_stripe_failure_still_creates_the_account_and_profile(self):
        self.create_account.side_effect = StripeCallError("Stripe is down.")

        response = self.signup()

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        user = User.objects.get(email="ada@example.com")
        self.assertFalse(Seller.objects.filter(user=user).exists())
        self.assertEqual(user.stripe_provision_error, "Stripe is down.")
        self.assertEqual(payload["stripe"], {"status": "failed", "error": "Stripe is down."})
        self.assertEqual(payload["browser_profile"]["status"], "ready")
        self.assertEqual(payload["browser_profile"]["profile_id"], "prof_1")
        self.assertTrue(payload["token"])

    def test_provision_retries_stripe_without_a_second_profile(self):
        self.create_account.side_effect = StripeCallError("Stripe is down.")
        signup = self.signup()
        token = signup.json()["token"]
        listed_after_signup = len(self.browser.listed)
        self.create_account.side_effect = None
        self.create_account.return_value = ("acct_456", "pending")

        response = self.client.post(
            "/api/accounts/provision/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        user = User.objects.get(email="ada@example.com")
        self.assertEqual(payload["stripe"]["stripe_account_id"], "acct_456")
        self.assertEqual(payload["stripe"]["onboarding_url"], ONBOARDING_URL)
        self.assertEqual(user.stripe_provision_error, "")
        self.assertEqual(len(self.browser.created), 1)
        self.assertEqual(len(self.browser.listed), listed_after_signup)
        self.assertEqual(payload["browser_profile"]["profile_id"], "prof_1")

    def test_login_rotates_the_token_and_logout_rejects_it(self):
        first = self.signup().json()["token"]
        login = self.client.post(
            "/api/accounts/login/",
            data=json.dumps({"email": "ada@example.com", "password": PASSWORD}),
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)
        second = login.json()["token"]
        self.assertNotEqual(second, first)
        self.assertEqual(ApiToken.objects.count(), 1)

        stale = self.client.get(
            "/api/stripe/connect/status/",
            HTTP_AUTHORIZATION=f"Bearer {first}",
        )
        self.assertEqual(stale.status_code, 401)

        logout = self.client.post(
            "/api/accounts/logout/",
            HTTP_AUTHORIZATION=f"Bearer {second}",
        )
        self.assertEqual(logout.status_code, 204)
        rejected = self.client.get(
            "/api/stripe/connect/status/",
            HTTP_AUTHORIZATION=f"Bearer {second}",
        )
        self.assertEqual(rejected.status_code, 401)

    def test_payments_connect_accepts_an_accounts_token(self):
        token = self.signup().json()["token"]

        response = self.client.post(
            "/api/stripe/connect/",
            data=json.dumps(
                {"display_name": "Ada", "contact_email": "ada@example.com"}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["stripe_account_id"], "acct_123")
        self.assertEqual(response.json()["onboarding_url"], ONBOARDING_URL)

    def test_unknown_login_matches_wrong_password(self):
        self.signup()
        wrong = self.client.post(
            "/api/accounts/login/",
            data=json.dumps({"email": "ada@example.com", "password": "nope-nope-nope"}),
            content_type="application/json",
        )
        missing = self.client.post(
            "/api/accounts/login/",
            data=json.dumps({"email": "missing@example.com", "password": PASSWORD}),
            content_type="application/json",
        )
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.json(), missing.json())

    def test_duplicate_email_and_weak_password(self):
        self.signup()
        duplicate = self.signup()
        weak = self.signup(email="other@example.com", password="short")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(weak.status_code, 400)

    def test_reuses_a_browser_profile_found_by_user_id(self):
        user = User.objects.create_user(
            email="ada@example.com", display_name="Ada", password=PASSWORD
        )
        token = ApiToken.objects.create(user=user)
        existing = Profile(
            id="prof_existing",
            created_at="t",
            updated_at="t",
            user_id=str(user.pk),
            name="Ada",
        )
        self.browser.profiles.append(existing)

        response = self.client.post(
            "/api/accounts/provision/",
            HTTP_AUTHORIZATION=f"Bearer {token.key}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["browser_profile"]["profile_id"], "prof_existing")
        self.assertEqual(self.browser.created, [])
        user.refresh_from_db()
        self.assertEqual(user.browser_profile_id, "prof_existing")


class RecipientIdempotencyTests(TestCase):
    def test_create_recipient_uses_the_user_id_as_the_idempotency_key(self):
        account = SimpleNamespace(id="acct_test")
        with patch("payments.stripe_api.client") as client:
            client.return_value.v2.core.accounts.create.return_value = account
            account_id, status = create_recipient_account(
                display_name="Ada",
                contact_email="ada@example.com",
                user_id=7,
            )
        self.assertEqual(account_id, "acct_test")
        self.assertEqual(status, "pending")
        options = client.return_value.v2.core.accounts.create.call_args.args[1]
        self.assertEqual(options["idempotency_key"], "salt-user-7")
        self.assertEqual(options["stripe_version"], "2026-08-26.preview")
