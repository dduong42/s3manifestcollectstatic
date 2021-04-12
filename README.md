# s3manifestcollectstatic

Optimized collectstatic for S3ManifestStaticStorage

## Installation

1. Install the package
```
pip install s3manifestcollectstatic
```
2. Add `s3manifestcollectstatic` to `INSTALLED_APPS`

## Description

`collectstatic` can take a long time. When used with
`storages.backends.s3boto3.S3ManifestStaticStorage`, `collectstatic` uploads
the files twice, once without the hash at the end of the file name, and once
with the hash.  Also, it doesn't use multiple threads to upload to s3.

`s3manifestcollectstatic` uploads the files only once, uses threads to speed
things up, and doesn't upload the files that are already on S3.

collectstatic: (Around 20 minutes)

```
$ time ./manage.py collectstatic --noinput

604 static files copied, 646 post-processed.
./manage.py collectstatic --noinput  29,94s user 2,27s system 2% cpu 20:25,06 total
```

s3manifestcollectstatic: (Around 30 seconds)
```
$ time ./manage.py s3manifestcollectstatic

604 static files copied to '/tmp/tmpbw0q_5lq', 646 post-processed.
Start the upload of 604 files
Uploading the manifest
./manage.py s3manifestcollectstatic  10,95s user 1,92s system 49% cpu 26,269 total
```

If you want to reupload the files use `-f`:
```
./manage.py s3manifestcollectstatic -f
```

Tested with Python 3.9, Django 3.2, django-storages 1.11
