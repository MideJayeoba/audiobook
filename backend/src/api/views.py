import os
import tempfile
from pathlib import Path

from django.http import HttpResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.core.files.uploadedfile import UploadedFile

from services.extraction import extract_text_from_pdf
from services.ai_navigation import detect_chapters_ai
from services.tts import synthesize_speech, get_edge_voice_options

@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(_request):
    return Response({"status": "ok", "service": "django-api-stateless"})

@api_view(["POST"])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser])
def extract_document(request):
    file: UploadedFile = request.FILES.get("source_file")
    if not file:
        return Response({"detail": "source_file is required"}, status=400)
    
    try:
        text = extract_text_from_pdf(file.file)
        return Response({"text": text})
    except Exception as e:
        return Response({"detail": str(e)}, status=500)

@api_view(["POST"])
@permission_classes([AllowAny])
def ai_sections(request):
    text = request.data.get("text", "")
    if not text:
        return Response({"detail": "text is required"}, status=400)
    
    try:
        result = detect_chapters_ai(text)
        return Response(result)
    except Exception as e:
        return Response({"detail": str(e)}, status=500)

@api_view(["POST"])
@permission_classes([AllowAny])
def tts_stream(request):
    text = request.data.get("text", "")
    voice = request.data.get("voice", "en-NG-AbeoNeural")
    if not text:
        return Response({"detail": "text is required"}, status=400)
        
    try:
        # Edge-TTS is the deployment provider (neural voices, incl. Nigerian
        # accents). gTTS/espeak remain as local-dev fallbacks only.
        result = synthesize_speech(text, voice, preferred_provider="edge")

        def file_iterator(file_path: Path):
            with file_path.open('rb') as f:
                while chunk := f.read(8192):
                    yield chunk
            # cleanup after sending
            try:
                file_path.unlink()
            except OSError:
                pass
                
        response = StreamingHttpResponse(file_iterator(result.audio_path), content_type="audio/mpeg")
        response['Content-Disposition'] = f'inline; filename="{result.audio_path.name}"'
        return response
    except Exception as e:
        return Response({"detail": str(e)}, status=500)

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import uuid
from services.tts import stream_edge_tts

_TTS_PREPARE_CACHE = {}

@csrf_exempt
def prepare_tts(request):
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)
    try:
        body = json.loads(request.body)
        token = str(uuid.uuid4())
        _TTS_PREPARE_CACHE[token] = body
        return JsonResponse({"token": token})
    except Exception as e:
        return JsonResponse({"detail": str(e)}, status=500)

@csrf_exempt
async def tts_stream_direct(request):
    try:
        if request.method == "GET":
            token = request.GET.get("token")
            if not token:
                return JsonResponse({"detail": "token required"}, status=400)
            body = _TTS_PREPARE_CACHE.get(token)
            if not body:
                return JsonResponse({"detail": "invalid or expired token"}, status=404)
        else:
            body = json.loads(request.body)
            
        text = body.get("text", "")
        voice = body.get("voice", "en-NG-AbeoNeural")
        
        if not text:
            return JsonResponse({"detail": "text is required"}, status=400)
            
        response = StreamingHttpResponse(stream_edge_tts(text, voice), content_type="audio/mpeg")
        response['Content-Disposition'] = 'inline; filename="stream.mp3"'
        return response
    except Exception as e:
        return JsonResponse({"detail": str(e)}, status=500)

@api_view(["GET"])
@permission_classes([AllowAny])
def voices_list(request):
    return Response({"voices": get_edge_voice_options()})
