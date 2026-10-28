import requests


BASE_URL = "https://hotel.gswack.com"


def test_create_reservation():
    payload = {
        "hotelId": "5",
        "fullName": "Test User6",
        "email": "test6@test.com",
        "checkIn": "2026-08-04",
        "checkOut": "2026-08-05"
    }

    response = requests.post(
        f"{BASE_URL}/reservations",
        json=payload
    )

    assert response.status_code == 200, \
        f"Expected status code 200, but got {response.status_code}"
    assert "successfully" in response.json()["message"], \
        f"Expected success message, but got {response.json()['message']}"
    