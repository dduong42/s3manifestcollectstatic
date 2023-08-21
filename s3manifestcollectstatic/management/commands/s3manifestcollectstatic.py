import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.staticfiles.management.commands import collectstatic
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage, staticfiles_storage
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

    def handle(self, *args, **options):
        self.force = options["force"]
        self.verbosity = options["verbosity"]
        self.max_workers = options["max_workers"]
        if self.max_workers is not None and self.max_workers <= 0:
            raise CommandError("The maximum number of workers must be greater than 0.")

        with TemporaryDirectory() as tmpdirname:
            command = collectstatic.Command()
            command.storage = ManifestStaticFilesStorage(location=tmpdirname)
            call_command(command)

            manifest = Path(tmpdirname) / MANIFEST_PATH
            with manifest.open("rb") as f:
                to_upload = set(json.load(f)["paths"].values())

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
