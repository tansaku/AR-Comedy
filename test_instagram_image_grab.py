import requests
from PIL import Image
from io import BytesIO


def get_profile_picture(access_token):
    url = f"https://graph.instagram.com/me?fields=profile_picture_url&access_token={access_token}"
    response = requests.get(url)
    data = response.json()

    if "profile_picture_url" in data:
        pic_url = data["profile_picture_url"]
        pic_response = requests.get(pic_url)
        img = Image.open(BytesIO(pic_response.content))
        img.save("profile_picture.jpg")
        print("Profile picture downloaded successfully.")
    else:
        # currently fails - probably permissions ...
        print("Failed to retrieve profile picture URL.")


# Use your access token
access_token = "IGQWRNSWdwU2RReWtHeGlYRlFrczdVRnBiZAGI0c3NnRU82R0hrWDIzamhsWFluRDFSenk1LVJsTVBlWmNNMGEwYW1TSmRRc3JrNVBxSnpwdmRrVE42VS1HVU8zZATF5djJjeHplRGE3Y1lYZAG9XMnlvd2FhTmVfVU0ZD"

get_profile_picture(access_token)
