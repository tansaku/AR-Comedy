import requests


def test_instagram_token(access_token, username):
    # Instagram Graph API endpoint for user info
    url = (
        f"https://graph.instagram.com/me?fields=id,username&access_token={access_token}"
    )

    try:
        response = requests.get(url)
        data = response.json()

        if "id" in data and "username" in data:
            print(f"Successfully connected to Instagram account:")
            print(f"User ID: {data['id']}")
            print(f"Username: {data['username']}")

            if data["username"].lower() == username.lower():
                print("Username matches the expected username.")
            else:
                print(
                    f"Warning: Username from API ({data['username']}) doesn't match expected username ({username})."
                )
        else:
            print("Failed to retrieve user data. Response:")
            print(data)

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")


# Replace with your actual access token
access_token = "IGQWRNSWdwU2RReWtHeGlYRlFrczdVRnBiZAGI0c3NnRU82R0hrWDIzamhsWFluRDFSenk1LVJsTVBlWmNNMGEwYW1TSmRRc3JrNVBxSnpwdmRrVE42VS1HVU8zZATF5djJjeHplRGE3Y1lYZAG9XMnlvd2FhTmVfVU0ZD"

# Your Instagram username
username = "tansaku"

test_instagram_token(access_token, username)
