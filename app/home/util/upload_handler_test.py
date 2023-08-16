import pytest
import os
import shutil

from ..test.factories import FileFactory

from upload_handler import route


def parse_image_meta_integration_test():
    shutil.copy("test_img.jpg", "test.jpg")
    with open("test.jpg") as f:
        file = FileFactory(file=f)
    file = route(file)
    os.remove("test.jpg")
