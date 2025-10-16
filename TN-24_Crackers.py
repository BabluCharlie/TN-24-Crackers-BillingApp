import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import os

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="TN-24 Crackers Billing App",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------
# CUSTOM CSS
# -----------------------------
st.markdown(
    """
    <style>
    .stApp { background-color: #d0f0c0; color: #033d00; }
    .stTextInput>div>div>input { border-radius: 8px; padding: 8px; }
    div.stButton > button { background-color: #4CAF50; color: white; border-radius: 8px; padding: 10px 20px; font-size: 16px; }
    .dataframe thead th { background-color: #4CAF50; color: white; }
    </style>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# GOOGLE SHEET CONNECTION
# -----------------------------
JSON_FILE = "tn-24-crackers-583ad6c889a7.json"

if not os.path.exists(JSON_FILE):
    st.warning(
        f"""
        ⚠️ Service account JSON not found: `{JSON_FILE}`  

        **Instructions to fix:**  
        1. Go to Google Cloud Console → IAM & Admin → Service Accounts.  
        2. Select your service account → Keys → Add Key → Create New JSON.  
        3. Download the JSON file and place it in your project folder:  
        `{os.getcwd()}`  
        4. Rename the file exactly: `{JSON_FILE}`  
        5. Share your Google Sheet 'BillingApp' with the service account email as **Editor**.  

        Once done, refresh this app.
        """
    )
    st.stop()

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

try:
    creds = Credentials.from_service_account_file(JSON_FILE, scopes=scope)
    client = gspread.authorize(creds)
    product_sheet = client.open("BillingApp").worksheet("Products")
    billing_sheet = client.open("BillingApp").worksheet("Billing")
except Exception as e:
    st.error(
        f"❌ Failed to connect to Google Sheets. Please check your JSON credentials and spreadsheet access.\n\nError details: {e}"
    )
    st.stop()

# -----------------------------
# STREAMLIT APP
# -----------------------------
st.title("🧾 TN-24 Crackers Billing App")
st.subheader("Create New Invoice")

# -----------------------------
# Load Products Dynamically
# -----------------------------
@st.cache_data(ttl=10)
def load_products():
    df = pd.DataFrame(product_sheet.get_all_records())
    df["Product ID"] = df["Product ID"].astype(str).str.strip()
    return df

products_df = load_products()

# -----------------------------
# Customer Info
# -----------------------------
st.markdown("### 👤 Customer Information")
customer_name = st.text_input("Customer Name")
customer_mobile = st.text_input("Mobile Number")
payment_mode = st.selectbox(
    "Payment Mode",
    options=["Cash", "UPI", "Card", "Bank Transfer"]
)
st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------
# Invoice Items State
# -----------------------------
if "invoice_items" not in st.session_state:
    st.session_state.invoice_items = []

# -----------------------------
# Add Products to Invoice
# -----------------------------
st.markdown("### 🛒 Add Products to Invoice")
selected_product_name = st.selectbox("Select Product", products_df["Product Name"])
quantity = st.number_input("Quantity", min_value=1, max_value=1000, step=1)

if st.button("➕ Add Product"):
    product_row = products_df[products_df["Product Name"] == selected_product_name].iloc[0]
    invoice_item = {
        "Product ID": str(product_row["Product ID"]).strip(),
        "Product Name": product_row["Product Name"],
        "Quantity": int(quantity),
        "Unit Price": float(product_row["Unit Price"]),
        "Total": int(quantity) * float(product_row["Unit Price"])
    }
    st.session_state.invoice_items.append(invoice_item)
    st.success(f"Added {quantity} x {selected_product_name} to invoice!")

st.markdown("<br>", unsafe_allow_html=True)

# -----------------------------
# Display Invoice Summary
# -----------------------------
if st.session_state.invoice_items:
    st.subheader("🧾 Invoice Summary")
    invoice_df = pd.DataFrame(st.session_state.invoice_items)
    grand_total = invoice_df["Total"].sum()
    st.dataframe(invoice_df, use_container_width=True)
    st.markdown(f"### 💰 Grand Total: ₹ {grand_total:,.2f}")
    st.markdown(f"**Payment Mode:** {payment_mode}")

    # -----------------------------
    # Save Invoice
    # -----------------------------
    if st.button("✅ Save Invoice"):
        if not customer_name or not customer_mobile:
            st.error("Please enter Customer Name and Mobile Number before saving!")
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for item in st.session_state.invoice_items:
                try:
                    # Safe Stock Update
                    current_cell = product_sheet.find(str(item["Product ID"]))
                    current_stock = int(product_sheet.cell(current_cell.row, 5).value)
                    if item["Quantity"] > current_stock:
                        st.warning(f"⚠️ Not enough stock for {item['Product Name']}. Skipping this item.")
                        continue
                    new_stock = current_stock - int(item["Quantity"])
                    product_sheet.update_cell(current_cell.row, 5, new_stock)
                    product_sheet.update_cell(current_cell.row, 6, new_stock * float(item["Unit Price"]))
                except Exception as e:
                    st.error(f"Error updating stock for {item['Product Name']}: {e}")
                    continue

                # Append to Billing Sheet
                billing_sheet.append_row([
                    str(now),
                    str(customer_name),
                    str(customer_mobile),
                    payment_mode,
                    str(item["Product ID"]),
                    str(item["Product Name"]),
                    int(item["Quantity"]),
                    float(item["Unit Price"]),
                    float(item["Total"])
                ])
            st.success("✅ Invoice saved and stock updated successfully!")

else:
    st.info("Add products to the invoice using the search box above.")
