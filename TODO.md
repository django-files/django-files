# TODO

## TopDos

-   [ ] Review ALL the `get_url` methods in the Files Model
-   [ ] Add tests for S3 functions

## TopBugs

-   [ ] The SITE_URL is still used as a setting value some places, and as a SiteSettings in others
-   [ ] Add a Warning to the site until the SITE_URL has been updated

## TopShues

-   [ ] Users: Fix Local User to allow Discord Webhook
-   [ ] Look into duplicate setup.cfg files

## Testing

-   [ ] Test API endpoint with token
-   [ ] Test Settings Form with Playwright
-   [ ] Test Flush Cache and Logout with Playwright
-   [ ] Test Oauth Flow

## General/UI

-   [ ] Gallery Overhaul
-   [ ] Go through environment variables and determine which ones should be configurable

## Files and Upload

-   [ ] Add File Viewing Endpoints for Stats and Embeds
-   [ ] Max Views Feature
-   [ ] Overhaul /shorten and /upload URL Endpoints

## Preview Page

-   [ ] Fix Image Preview for Images not Browser Compatible (heic)

## Site Settings

-   [ ] Add OAuth Variables to SiteSettings
-   [ ] Add S3 Variables to SiteSettings
-   [ ] Full Settings Interface Overhaul
-   [ ] Custom Favicon + Logo Feature

## Stats

-   [ ] Add File Views to Stats
-   [ ] Add Shorts Views to Stats
-   [ ] Move Stats Generation to Template Tag for Caching
-   [ ] Update Stats Graphs and Generate More

## Miscellaneous

-   [ ] Finish optimizing build image first =D
-   [ ] Auto configure CORS on s3 bucket on init?
-   [ ] Example IAM settings for s3 user, plus guide on setup.
