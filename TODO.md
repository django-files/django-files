# TODO

## TopDos
- [ ] Review ALL the `get_url` methods in the Files Model
- [ ] Look into `utils.s3` and `utils.storage` files
- [ ] Add tests for `/raw/` and other S3 functions

## TopBugs
- [ ] The SITE_URL is still used as a setting value some places, and as a SiteSettings in others
- [ ] Add a Warning to the site until the SITE_URL has been updated

## TopShues
- [ ] Users: Fix Local User to allow Discord Webhook
- [ ] Overhaul Image Processing Tasks in `util`
- [ ] Look into duplicate setup.cfg files

## Testing
- [ ] Test API endpoint with token
- [ ] Test Settings Form with Playwright
- [ ] Test Flush Cache and Logout with Playwright
- [ ] Test Vector Tasks
- [ ] Test Oauth Flow

## Users
- [ ] Add User Invites

## General/UI
- [ ] Avatars for Local Users
- [ ] Gallery Overhaul
- [ ] Go through environment variables and determine which ones should be configurable

## Files and Upload
- [ ] Add File Viewing Endpoints for Stats and Embeds
- [ ] Max Views Feature
- [ ] Filename Options Feature
- [ ] Overhaul /shorten and /upload URL Endpoints
- [ ] Option to strip exif on upload regardless of user settings.
- [ ] Bulk delete on files list.

## Preview Page
- [ ] Fix Image Preview for Images not Browser Compatible (heic)

## Site Settings
- [ ] Add OAuth Variables to SiteSettings
- [ ] Add S3 Variables to SiteSettings
- [ ] Full Settings Interface Overhaul
- [ ] Custom Favicon Feature
- [ ] Custom Login Screen Feature

## Stats
- [ ] Add File Views to Stats
- [ ] Add Shorts Views to Stats
- [ ] Move Stats Generation to Template Tag for Caching
- [ ] Update Stats Graphs and Generate More

## API
- [ ] Files - GET files
- [ ] Stats - GET stats
- [ ] Users - GET PUT DELETE users

## Passwords and Private Files
- [ ] Add support for nginx raw files to have signed urls.
- [ ] Auto add password query string to preview/raw url clipboard buttons when pw set
- [ ] Better access denied error page.

## Miscellaneous
- [ ] Finish optimizing build image first =D
- [ ] Add Demo Mode and launch Demo
- [ ] Auto configure CORS on s3 bucket on init.
- [ ] Example IAM settings for s3 user, plus guide on setup.
