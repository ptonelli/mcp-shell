import io
import os
import mimetypes
from typing import Union, Annotated
from pydantic import Field
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.utilities.types import Image
from mcp.types import ImageContent
from app.context import get_session_cwd
from app.security import is_safe_path

def get_image(
    ctx: Context,
    path: Annotated[str, Field(description="Path to the image file")]
) -> Union[ImageContent, dict]:
    """Get an image from the specified path, compressed if large."""
    cwd = get_session_cwd(ctx)
    abs_path = os.path.normpath(os.path.join(cwd, path))

    if not is_safe_path(abs_path):
        return {"success": False, "error": "Unauthorized path"}
    if not os.path.isfile(abs_path):
        return {"success": False, "error": f"File '{path}' not found"}

    try:
        mime_type, _ = mimetypes.guess_type(abs_path)
        if not mime_type or not mime_type.startswith('image/'):
            return {"success": False, "error": "Not a recognized image format"}

        file_size = os.path.getsize(abs_path)
        ext = os.path.splitext(abs_path)[1].lower().lstrip('.')
        if ext in ('jpg', 'jpeg'): ext = 'jpeg'

        if file_size > 1000000:
            from PIL import Image as PILImage
            buffer = io.BytesIO()
            img = PILImage.open(abs_path)
            img.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
            return Image(data=buffer.getvalue(), format="jpeg").to_image_content()
        else:
            with open(abs_path, 'rb') as f:
                return Image(data=f.read(), format=ext).to_image_content()
    except Exception as e:
        return {"success": False, "error": str(e)}
