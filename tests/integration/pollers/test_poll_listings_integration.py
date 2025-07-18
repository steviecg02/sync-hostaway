from sync_hostaway.pollers.listings import poll_listings


def test_poll_listings_integration_real_hostaway() -> None:
    """
    Run poll_listings against real Hostaway API and check it returns listing data.
    """
    listings = poll_listings()

    print("Returned listings:", listings)

    assert isinstance(listings, list)
    assert listings, "No listings returned"
    assert isinstance(listings[0], dict)
    assert "id" in listings[0]
