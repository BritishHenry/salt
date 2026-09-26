"""Marketplace account connection.

Connects and refreshes the seller's Vinted, Depop, and eBay sessions. A
password is encrypted before the browser run and bound to that marketplace
only. Cookies stay on the seller's profile. Salt is told when a login needs
the seller again, before Maggie can publish.
"""
