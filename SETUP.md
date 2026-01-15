# Mezze Sheet Driver Setup

## Prerequisites

1. Python 3.9+
2. Google Cloud project with Sheets API enabled
3. Service account with access to the Mezze sheet

## Quick Setup

### 1. Install Dependencies

```bash
cd "/Users/djwawa/mff mrayeh"
pip install -r requirements.txt
```

### 2. Create Service Account (One-time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create one for `mamnoonrestaurant.com`)
3. Navigate to **IAM & Admin** → **Service Accounts**
4. Click **Create Service Account**
   - Name: `mezze-sheet-reader`
   - ID: `mezze-sheet-reader` (auto-generated)
   - Click **Create and Continue**
   - Skip role assignment (not needed for Sheets API)
   - Click **Done**

5. Click on the new service account
6. Go to **Keys** tab → **Add Key** → **Create new key**
7. Select **JSON** → **Create**
8. Save the downloaded file as: `config/service-account.json`

### 3. Share the Sheet

1. Open the Mezze Sheet in Google Sheets
2. Click **Share**
3. Add the service account email (looks like):
   ```
   mezze-sheet-reader@your-project-id.iam.gserviceaccount.com
   ```
4. Set permission to **Viewer**
5. Click **Send** (uncheck "Notify people" if prompted)

### 4. Enable Sheets API (if not already)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Library**
3. Search for "Google Sheets API"
4. Click **Enable**

### 5. Test the Driver

```bash
python test_mezze.py
```

Expected output:
```
============================================================
MEZZE SHEET DRIVER TEST
============================================================

✓ Credentials file found: config/service-account.json
✓ Sheet ID: 1gsDSGjrE7bvOhITgU-S2Q_kTHw6OCrNPAfKHg6AF3XE

------------------------------------------------------------
TEST 1: List all tabs
------------------------------------------------------------

✓ Successfully connected! Found XX tabs:

Weekly Order Tabs:
  📅 01/12-01/16 Weekly Order
  📅 01/05-01/09 Weekly Order
  ...

------------------------------------------------------------
TEST 2: Fetch recent orders (last 2 weeks)
------------------------------------------------------------

✓ Fetch successful!

Stats:
  Tabs processed: X
  Raw lines: XXX
  Orders created: XX
  ...

============================================================
✓ ALL TESTS PASSED
============================================================
```

## Troubleshooting

### "Credentials file not found"
- Make sure `config/service-account.json` exists
- Check the file path in the error message

### "Permission denied" or "404 Not Found"
- The sheet is not shared with the service account
- Go to the sheet → Share → Add the service account email

### "Sheets API has not been used" or "API not enabled"
- Enable the Google Sheets API in Cloud Console
- APIs & Services → Library → Search "Sheets" → Enable

### "Invalid credentials"
- The JSON file may be corrupted or for a different project
- Re-download the service account key

## File Structure

```
mff mrayeh/
├── config/
│   ├── .gitignore           # Keeps credentials out of git
│   └── service-account.json # YOUR SERVICE ACCOUNT KEY (create this)
├── src/
│   └── drivers/
│       └── google_sheets_driver.py
├── requirements.txt
├── test_mezze.py
└── SETUP.md
```
