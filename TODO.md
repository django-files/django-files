# TODO

## TopDos
- [ ] Rework the `get_url` function in the Files Model
- [ ] Look into `utils.s3` and `utils.storage` files
- [ ] Add tests for `/raw/` and other S3 functions

## TopBugs
- [ ] The site does not work unless a proper SITE_URL is set.

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

## General/UI
- [ ] Gallery Overhaul
- [ ] Go through environment variables and determine which ones should be configurable

## Files and Upload
- [ ] Add File Viewing Endpoints for Stats and Embeds
- [ ] Password Protection Feature
- [ ] Max Views Feature
- [ ] Filename Options Feature
- [ ] Overhaul /shorten and /upload URL Endpoints
- [ ] Option to strip exif on upload regardless of user settings.

## Preview Page
- [ ] Fix Image Preview for Images not Browser Compatible (heic)

## Site Settings
- [ ] Add OAuth Variables to SiteSettings
- [ ] Add S3 Variables to SiteSettings
- [ ] Full Settings Interface Overhaul
- [ ] Custom Site Title Feature
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

## Miscellaneous
- [ ] Finish optimizing build image first =D
- [ ] Add Demo Mode and launch Demo
- [ ] Auto configure CORS on s3 bucket on init.
- [ ] Example IAM settings for s3 user, plus guide on setup.
