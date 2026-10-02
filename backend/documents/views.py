from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from families.models import Family
from . import services
from .models import Document
from .serializers import DocumentSerializer


class DocumentListUploadView(APIView):
    """GET -> the documents this keeper may see; POST (multipart: file, title, kind, family_id?) -> upload."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        scope = services.document_scope(request.user)
        if scope is None:
            return Response({"detail": "Your role does not keep documents."}, status=status.HTTP_403_FORBIDDEN)
        return Response({"level": scope[0], "family_name": scope[1].name if scope[1] else None, "documents": DocumentSerializer(services.visible_documents(user=request.user), many=True).data})

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Choose a file to upload."}, status=status.HTTP_400_BAD_REQUEST)
        family = None
        if request.data.get("family_id"):
            family = get_object_or_404(Family, id=request.data.get("family_id"), community=request.user.community)
        try:
            doc = services.upload_document(user=request.user, upload=upload, title=request.data.get("title", ""), kind=request.data.get("kind", "other"), family=family)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages if hasattr(exc, "messages") else str(exc)}, status=status.HTTP_403_FORBIDDEN if "role" in str(exc) else status.HTTP_400_BAD_REQUEST)
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class DocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        doc = get_object_or_404(Document, id=document_id)
        if not services.can_download(request.user, doc):
            return Response({"detail": "You cannot open this document."}, status=status.HTTP_403_FORBIDDEN)
        return FileResponse(doc.file.open("rb"), as_attachment=True, filename=doc.original_name or doc.file.name.rsplit("/", 1)[-1])

    def delete(self, request, document_id):
        doc = get_object_or_404(Document, id=document_id)
        try:
            services.delete_document(user=request.user, document=doc)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages if hasattr(exc, "messages") else str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)
