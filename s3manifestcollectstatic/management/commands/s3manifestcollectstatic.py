import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from django import VERSION
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

MANIFEST_PATH = "staticfiles.json"


class Command(BaseCommand):
    def log(self, msg, level=2):
        """
        Small log helper
        """
        if self.verbosity >= level:
            self.stdout.write(msg)

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Force the reupload of files",
        )
        parser.add_argument(
            "-w",
            "--max-workers",
            type=int,
            help="Max number of workers",
        )

    @staticmethod
    def get_staticfiles_storage():
        if VERSION < (4, 2):
            from django.core.files.storage import get_storage_class

            return get_storage_class(settings.STATICFILES_STORAGE)()
        else:
            from django.conf import STATICFILES_STORAGE_ALIAS
            from django.core.files.storage import StorageHandler

            return StorageHandler()[STATICFILES_STORAGE_ALIAS]

    @staticmethod
    @contextmanager
    def override_storage_settings(static_root, staticfiles_storage):
        saved_static_root = settings.STATIC_ROOT
        settings.STATIC_ROOT = static_root

        if VERSION < (4, 2) or settings.is_overridden("STATICFILES_STORAGE"):
            saved_storage = settings.STATICFILES_STORAGE
            settings.STATICFILES_STORAGE = staticfiles_storage
            yield
            settings.STATICFILES_STORAGE = saved_storage
        else:
            saved_storage = settings.STORAGES
            settings.STORAGES = {
                **saved_storage,
                "staticfiles": {
                    "BACKEND": staticfiles_storage,
                },
            }
            yield
            settings.STORAGES = saved_storage

        settings.STATIC_ROOT = saved_static_root

    def handle(self, *args, **options):
        self.force = options["force"]
        self.verbosity = options["verbosity"]
        self.max_workers = options["max_workers"]
        if self.max_workers is not None and self.max_workers <= 0:
            raise CommandError("The maximum number of workers must be greater than 0.")

        with TemporaryDirectory() as tmpdirname:
            with self.override_storage_settings(
                tmpdirname,
                staticfiles_storage="django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
            ):
                call_command("collectstatic")

            manifest = Path(tmpdirname) / MANIFEST_PATH
            with manifest.open("rb") as f:
                to_upload = set(json.load(f)["paths"].values())

            staticfiles_storage = self.get_staticfiles_storage()
            if staticfiles_storage.exists(MANIFEST_PATH):
                with staticfiles_storage.open(MANIFEST_PATH) as f:
                    already_uploaded = set(json.load(f)["paths"].values())
                    intersection = to_upload.intersection(already_uploaded)
                    self.log(f"{len(intersection)} files were already uploaded", level=1)

                    if self.force:
                        self.log("Forcing the reupload of files", level=1)
                    else:
                        to_upload.difference_update(already_uploaded)

            def _save_asset(path):
                path_obj = Path(tmpdirname) / path
                with path_obj.open("rb") as f:
                    staticfiles_storage.save(path, f)
                return path

            self.log(f"Start the upload of {len(to_upload)} files", level=1)
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                for path in executor.map(_save_asset, to_upload):
                    self.log(f"{path} was uploaded", level=2)

            # Save manifest in the end when everything succeeded
            self.log("Uploading the manifest", level=1)
            _save_asset(MANIFEST_PATH)
