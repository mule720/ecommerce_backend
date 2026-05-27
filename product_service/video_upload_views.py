"""Video upload endpoints for product media workflows."""

import os
import shutil
import subprocess
import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


MAX_VIDEO_DURATION_SECONDS = 30 * 60
MAX_VIDEO_FILE_SIZE_BYTES = 500 * 1024 * 1024
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.m4v', '.mkv', '.avi'}
MAX_IMAGE_FILE_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def _build_media_file_url(request, saved_path: str) -> str:
    media_url = settings.MEDIA_URL
    if not media_url.startswith('/'):
        media_url = f'/{media_url}'
    return request.build_absolute_uri(f'{media_url}{saved_path}')


def _probe_video_duration_seconds(file_path: str):
    ffprobe_path = shutil.which('ffprobe')
    if not ffprobe_path:
        return None

    try:
        command = [
            ffprobe_path,
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return float((result.stdout or '').strip())
    except Exception:
        return None


@csrf_exempt
@require_POST
def upload_product_video(request):
    """Accepts a product video upload and validates the <= 30 minute rule."""
    uploaded_video = request.FILES.get('video')
    if not uploaded_video:
        return JsonResponse({'error': 'Video file is required.'}, status=400)

    content_type = str(getattr(uploaded_video, 'content_type', '') or '').lower()
    if not content_type.startswith('video/'):
        return JsonResponse({'error': 'Only video files are allowed.'}, status=400)

    if uploaded_video.size > MAX_VIDEO_FILE_SIZE_BYTES:
        return JsonResponse({'error': 'Video file is too large. Max supported size is 500MB.'}, status=400)

    extension = os.path.splitext(uploaded_video.name or '')[1].lower()
    if extension and extension not in ALLOWED_VIDEO_EXTENSIONS:
        return JsonResponse({'error': 'Unsupported video format.'}, status=400)

    raw_duration = request.POST.get('duration_seconds')
    try:
        duration_seconds = float(raw_duration)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Valid duration_seconds is required.'}, status=400)

    if duration_seconds <= 0:
        return JsonResponse({'error': 'Video duration must be greater than 0 seconds.'}, status=400)
    if duration_seconds > MAX_VIDEO_DURATION_SECONDS:
        return JsonResponse({'error': 'Video must not exceed 30 minutes.'}, status=400)

    safe_extension = extension or '.mp4'
    generated_name = f'{uuid.uuid4().hex}{safe_extension}'
    relative_path = f'products/videos/{generated_name}'
    saved_path = default_storage.save(relative_path, uploaded_video)

    try:
        absolute_path = default_storage.path(saved_path)
    except Exception:
        absolute_path = None

    if absolute_path:
        probed_duration = _probe_video_duration_seconds(absolute_path)
        if probed_duration is not None and probed_duration > MAX_VIDEO_DURATION_SECONDS:
            default_storage.delete(saved_path)
            return JsonResponse({'error': 'Uploaded video duration exceeds 30 minutes.'}, status=400)

    return JsonResponse(
        {
            'file_path': saved_path,
            'file_url': _build_media_file_url(request, saved_path),
            'duration_seconds': duration_seconds,
            'max_duration_seconds': MAX_VIDEO_DURATION_SECONDS,
        },
        status=201,
    )


@csrf_exempt
@require_POST
def upload_product_image(request):
    """Accepts a product image upload and stores it in media storage."""
    uploaded_image = request.FILES.get('image')
    if not uploaded_image:
        return JsonResponse({'error': 'Image file is required.'}, status=400)

    content_type = str(getattr(uploaded_image, 'content_type', '') or '').lower()
    if not content_type.startswith('image/'):
        return JsonResponse({'error': 'Only image files are allowed.'}, status=400)

    if uploaded_image.size > MAX_IMAGE_FILE_SIZE_BYTES:
        return JsonResponse({'error': 'Image file is too large. Max supported size is 10MB.'}, status=400)

    extension = os.path.splitext(uploaded_image.name or '')[1].lower()
    if extension and extension not in ALLOWED_IMAGE_EXTENSIONS:
        return JsonResponse({'error': 'Unsupported image format.'}, status=400)

    safe_extension = extension or '.jpg'
    generated_name = f'{uuid.uuid4().hex}{safe_extension}'
    relative_path = f'products/images/{generated_name}'
    saved_path = default_storage.save(relative_path, uploaded_image)

    return JsonResponse(
        {
            'file_path': saved_path,
            'file_url': _build_media_file_url(request, saved_path),
        },
        status=201,
    )
