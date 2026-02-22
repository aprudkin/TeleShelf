# tdl Setup & Authentication Design

**Date:** 2026-02-17
**Goal:** Install tdl CLI tool and authenticate via QR code for Telegram file downloading

## Context

[tdl](https://github.com/iyear/tdl) is a Go-based Telegram CLI toolkit (download, upload, forward, export). We need it installed and authenticated to download files from Telegram channels/chats.

## Environment

- macOS (Sequoia)
- Telegram Desktop installed from desktop.telegram.org (with local passcode)
- Homebrew available

## Authentication Method: QR Code

Chosen over Desktop session reuse to avoid session conflicts with Telegram Desktop.

`tdl login -T qr` displays a QR code in terminal. Scan with Telegram on phone (Settings > Devices > Link Desktop Device). Creates a separate session — no impact on existing Desktop client.

## Implementation Steps

1. Install tdl via Homebrew: `brew install telegram-downloader`
2. Verify installation: `tdl version`
3. Authenticate via QR: `tdl login -T qr` (interactive — requires user to scan QR)
4. Verify auth: `tdl chat ls`

## Post-Setup Usage

Download files:
```bash
# Single message
tdl dl -u https://t.me/channel/123

# Custom output directory
tdl dl -u https://t.me/channel/123 -d ~/Downloads

# Multiple links
tdl dl -u https://t.me/channel/1 -u https://t.me/channel/2
```

## Risks

- **Account restrictions**: tdl recommends using long-lived accounts; avoid aggressive parallelism settings
- **Rate limiting**: stick to defaults (`--threads 4 --limit 2`) initially
- **Time sync**: if "msg_id too high" errors occur, use `--ntp` flag
