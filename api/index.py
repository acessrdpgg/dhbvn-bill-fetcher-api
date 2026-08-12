import os
import random

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import requests
from bs4 import BeautifulSoup

app = FastAPI(
    title="DHBVN-Lens API",
    description="Asynchronous utility platform extracting DHBVN public context metadata",
    version="1.0.0"
)


# Core extraction logic mapping
def extract_dhbvn_data(account_no: str) -> dict:
    url = "https://epayment.dhbvn.org.in/b2cpaybill.aspx"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    session = requests.Session()
    session.headers.update(headers)

    try:
        # Step 1: Pull state fields
        response = session.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        viewstate = soup.find('input', {'id': '__VIEWSTATE'})['value']
        viewstate_gen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})['value']
        event_validation = soup.find('input', {'id': '__EVENTVALIDATION'})['value']

        # Step 2: Build parameters utilizing the dummy inputs
        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstate_gen,
            "__EVENTVALIDATION": event_validation,
            "__ControlsRequirePostBackKey__": [
                "Billdesk_net_banking_3", "Paytm_net_banking_2", "Sbi_net_banking", "indian_net_banking",
                "Paytm_upi_2", "Sbi_upi", "indian_upi", "Paytm_cards_2", "indina_cards", "Sbi_cards_1",
                "Paytm_cards_3", "indian_cards1", "Sbi_cards_2", "Paytm_cards_4", "indian_qr", "Sbi_cards_3",
                "Rtgs_with_challanYes", "Rtgs_with_challan", "Rtgs_without_challan"
            ],
            "txtAccountNo": account_no,
            "lblMobSearch": "",
            "txtmobile": "9988776655",
            "txtemail": "",
            "txtcaptcha": str(random.randint(1111, 9999)),  # Frontend bypass bypass token value
            "btnsubmit": "Proceed",
            "lblAcNo": "",
            "lblConsumerName": "",
            "lblAddress": "",
            "txtTransactionID": "",
            "txtIsConfirmed": "",
            "txtRegisteredMob": "",
            "txtIsMsgSend": ""
        }

        # Step 3: Run secure lookup request pipeline
        post_response = session.post(url, data=payload, timeout=15)
        post_response.raise_for_status()

        post_soup = BeautifulSoup(post_response.text, 'html.parser')

        lbl_ac_no = post_soup.find('input', {'id': 'lblAcNo'})
        account_out = lbl_ac_no['value'] if lbl_ac_no and 'value' in lbl_ac_no.attrs else None

        if not account_out:
            return {"success": False, "message": "Invalid Consumer Account Identification Number."}

        lbl_name = post_soup.find('input', {'id': 'lblConsumerName'})
        lbl_address = post_soup.find('textarea', {'id': 'lblAddress'})
        txt_amount = post_soup.find('span', {'id': 'txtAmount'})
        txt_trans = post_soup.find('input', {'id': 'txtTransactionID'})
        txt_reg_mob = post_soup.find('input', {'id': 'txtRegisteredMob'})

        return {
            "success": True,
            "data": {
                "account_number": account_out.strip(),
                "consumer_name": lbl_name['value'].strip() if lbl_name else "N/A",
                "address": lbl_address.text.strip() if lbl_address else "N/A",
                "amount_payable": txt_amount.text.strip() if txt_amount else "0",
                "transaction_id": txt_trans['value'].strip() if txt_trans else "N/A",
                "registered_mobile": txt_reg_mob['value'].strip() if txt_reg_mob else "N/A"
            }
        }

    except Exception as e:
        return {"success": False, "message": f"Core execution connection failure: {str(e)}"}


@app.get("/api/lookup")
async def lookup_account(
        account_no: str = Query(..., description="Target Consumer ID")
):
    result = extract_dhbvn_data(account_no)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# Route mappings resolving raw public components locally
public_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
if os.path.exists(public_dir):
    app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")