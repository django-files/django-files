# TODO

## 0.1.1

### ToDoS

-   Rework the `get_url` function in the Files Model
-   Look into `utils.s3` and `utils.storage` files
-   Add tests for `/raw/` and other S3 functions

### Known Bugs

-   Expiration has been disabled and not working
-   Info field has been disabled and should be reworked with expiration

## Testing

-   Test API endpoint with token
-   Test Settings Form with Playwright
-   Test Flush Cache and Logout with Playwright
-   Test Vector Tasks
-   Test Oauth Flow

## Issues
- [ ] Users: Fix Local User to allow Discord Webhook
- [ ] Overhaul Image Processing Tasks in `util`

## General/UI
- [ ] Gallery Overhaul

## Files and Upload
- [ ] Add File Viewing Endpoints for Stats and Embeds
- [ ] Password Protection Feature
- [ ] Max Views Feature
- [ ] Filename Options Feature
- [ ] Overhaul /shorten and /upload URL Endpoints
- [ ] Option to strip exif on upload regardless of user settings.

## Preview Page
- [ ] Overhaul EXIF Parsing to be a re-usable function
- [ ] Fix highlight.js for Light Mode
- [ ] Fix Image Preview for Images not Browser Compatible (heic)

## Site Settings
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
- [ ] Add Demo Mode and launch Demo
