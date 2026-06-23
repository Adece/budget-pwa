# Budget PWA

A mobile-first Progressive Web App for logging expenses to Google Sheets.
Installs to the iOS homescreen via Safari → Share → Add to Home Screen.

## Environment variables (Railway)

| Variable | Description | Example |
|---|---|---|
| `GOOGLE_SHEET_ID` | ID from the Sheet URL | `1BxiMVs0X...` |
| `GOOGLE_CREDENTIALS_JSON` | Full contents of credentials.json | `{"type":"service_account",...}` |
| `WHO_ME` | Your display name in the sheet | `Greg` |
| `WHO_HER` | Her display name in the sheet | `Ania` |
| `PORT` | Set automatically by Railway | — |

## Reuses the same Google Sheet as the Telegram bot

Both the Telegram bot and this PWA write to the same spreadsheet — 
same `GOOGLE_SHEET_ID` and `GOOGLE_CREDENTIALS_JSON` values.

## iOS install instructions

1. Open the Railway URL in **Safari** (not Chrome)
2. Tap the **Share** icon (box with arrow)
3. Tap **Add to Home Screen**
4. Tap **Add**

The app now lives on the homescreen with its own icon, opens full-screen with no browser chrome.
