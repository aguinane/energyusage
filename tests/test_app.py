from context import test_site


def test_index():
    """ Test some basic pages load correctly
    """
    response = test_site.get("/")
    assert response.status_code == 200

    response = test_site.get("/about/")
    assert response.status_code == 200
