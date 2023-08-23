# TODO

## 0.1.1

### Storge Issue Outline

1.  In its current setup, `default_storage.save()` creates the file in the media directory on ~69 [views.py](app/api/views.py)

For this first issue, we probably need to define a temporary storage, 
that the task can read into memory, save to media storage, then cleanup.
 
2.  Then a second file is created on ~109 [tasks.py](app%2Fhome%2Ftasks.py)

If the first issue uses an isolated storage, while we would be writing the file to disk twice, 
it should fix all issues with this part of the storage problem.

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
