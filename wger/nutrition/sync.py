# This file is part of wger Workout Manager.
#
# wger Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wger Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License

# Standard Library
import logging
import os
from typing import Optional

# Django
from django.conf import settings
from django.db import IntegrityError

# Third Party
import requests

# wger
from wger.nutrition.models import (
    Image,
    Ingredient,
    Source,
)
from wger.utils.constants import (
    DOWNLOAD_INGREDIENT_OFF,
    DOWNLOAD_INGREDIENT_WGER,
)
from wger.utils.requests import wger_headers


logger = logging.getLogger(__name__)

IMAGE_API = "{0}/api/v2/ingredient-image/"


def fetch_ingredient_image(pk: int):
    # wger
    from wger.nutrition.models import Ingredient

    ingredient = Ingredient.objects.get(pk=pk)
    logger.info(f'Fetching image for ingredient {pk}')

    if hasattr(ingredient, 'image'):
        return

    if ingredient.source_name != Source.OPEN_FOOD_FACTS.value:
        return

    if not ingredient.source_url:
        return

    if settings.TESTING:
        return

    if settings.WGER_SETTINGS['DOWNLOAD_INGREDIENT_IMAGES'] == DOWNLOAD_INGREDIENT_OFF:
        fetch_image_from_off(ingredient)
    elif settings.WGER_SETTINGS['DOWNLOAD_INGREDIENT_IMAGES'] == DOWNLOAD_INGREDIENT_WGER:
        fetch_image_from_wger_instance(ingredient)


def fetch_image_from_wger_instance(ingredient):
    url = f"{settings.WGER_SETTINGS['WGER_INSTANCE']}/api/v2/ingredient-image/{ingredient.pk}"
    result = requests.get(url, headers=wger_headers()).json()
    image_uuid = result['uuid']
    try:
        Image.objects.get(uuid=image_uuid)
        logger.info('image already present locally, skipping...')
        return
    except Image.DoesNotExist:
        retrieved_image = requests.get(result['image'], headers=wger_headers())
        Image.from_json(ingredient, retrieved_image, result)


def fetch_image_from_off(ingredient):
    # Everything looks fine, go ahead
    logger.info(f'Trying to fetch image from OFF for {ingredient.name} (UUID: {ingredient.uuid})')
    headers = wger_headers()

    # Fetch the product data
    product_data = requests.get(ingredient.source_url, headers=headers).json()
    image_url: Optional[str] = product_data['product'].get('image_front_url')
    if not image_url:
        logger.info('Product data has no "image_front_url" key')
        return
    image_data = product_data['product']['images']

    # Download the image file
    response = requests.get(image_url, headers=headers)
    if response.status_code != 200:
        logger.info(f'An error occurred! Status code: {response.status_code}')
        return

    # Parse the file name, looks something like this:
    # https://images.openfoodfacts.org/images/products/00975957/front_en.5.400.jpg
    image_name: str = image_url.rpartition("/")[2].partition(".")[0]

    # Retrieve the uploader name
    try:
        image_id: str = image_data[image_name]['imgid']
        uploader_name: str = image_data[image_id]['uploader']
    except KeyError as e:
        logger.info('could not load all image information, skipping...', e)
        return

    # Save to DB
    image_data = {
        'image': os.path.basename(image_url),
        'license_author': uploader_name,
        'size': len(response.content)
    }
    try:
        Image.from_json(ingredient, response, image_data, generate_uuid=True)
    # Due to a race condition (e.g. when adding tasks over the search), we might
    # try to save an image to an ingredient that already has one. In that case,
    # just ignore the error
    except IntegrityError:
        logger.info('Ingredient has already an image, skipping...')
        return
    logger.info('Image successfully saved')


def download_ingredient_images(
    print_fn,
    remote_url=settings.WGER_SETTINGS['WGER_INSTANCE'],
    style_fn=lambda x: x,
):
    headers = wger_headers()
    # Get all images
    page = 1
    all_images_processed = False
    result = requests.get(IMAGE_API.format(remote_url), headers=headers).json()
    print_fn('*** Processing images ***')
    while not all_images_processed:
        print_fn('')
        print_fn(f'*** Page {page}')
        print_fn('')

        for image_data in result['results']:
            image_uuid = image_data['uuid']

            print_fn(f'Processing image {image_uuid}')

            try:
                ingredient = Ingredient.objects.get(uuid=image_data['ingredient_uuid'])
            except Ingredient.DoesNotExist:
                print_fn('    Remote ingredient not found in local DB, skipping...')
                continue

            try:
                Image.objects.get(uuid=image_uuid)
                print_fn('    Image already present locally, skipping...')
                continue
            except Image.DoesNotExist:
                print_fn('    Image not found in local DB, creating now...')
                retrieved_image = requests.get(image_data['image'], headers=headers)
                Image.from_json(ingredient, retrieved_image, image_data)

            print_fn(style_fn('    successfully saved'))

        if result['next']:
            page += 1
            result = requests.get(result['next'], headers=headers).json()
        else:
            all_images_processed = True
