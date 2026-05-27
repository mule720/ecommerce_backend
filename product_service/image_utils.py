"""
Image optimization utilities
- WebP conversion
- Responsive image generation
- Image compression
"""
import os
import io
from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from pathlib import Path


class ImageOptimizer:
    """Optimize images for web delivery"""
    
    RESPONSIVE_SIZES = {
        'thumbnail': 200,
        'small': 400,
        'medium': 800,
        'large': 1200,
    }
    
    QUALITY_SETTINGS = {
        'webp': 80,
        'jpeg': 85,
    }
    
    @staticmethod
    def convert_to_webp(image_file, quality=80):
        """Convert image to WebP format"""
        try:
            img = Image.open(image_file)
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            
            output = io.BytesIO()
            img.save(output, format='WEBP', quality=quality)
            output.seek(0)
            return output
        except Exception as e:
            print(f"WebP conversion failed: {e}")
            return None
    
    @staticmethod
    def create_responsive_variants(image_file, filename):
        """Generate responsive image variants"""
        variants = {}
        
        try:
            img = Image.open(image_file)
            base_name = Path(filename).stem
            extension = '.webp'
            
            for size_name, width in ImageOptimizer.RESPONSIVE_SIZES.items():
                # Calculate height maintaining aspect ratio
                ratio = width / img.width
                height = int(img.height * ratio)
                
                # Resize and convert to WebP
                resized = img.resize((width, height), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                resized.save(
                    output,
                    format='WEBP',
                    quality=ImageOptimizer.QUALITY_SETTINGS['webp']
                )
                output.seek(0)
                
                # Save to storage
                filename_variant = f"{base_name}_{size_name}{extension}"
                path = default_storage.save(f"products/{filename_variant}", ContentFile(output.read()))
                variants[size_name] = path
            
            return variants
        except Exception as e:
            print(f"Responsive variant generation failed: {e}")
            return {}
    
    @staticmethod
    def get_srcset_string(base_variants):
        """Generate HTML srcset string for responsive images"""
        if not base_variants:
            return ""
        
        srcset_parts = []
        width_map = {
            'thumbnail': 200,
            'small': 400,
            'medium': 800,
            'large': 1200,
        }
        
        for size_name, path in base_variants.items():
            if size_name in width_map:
                srcset_parts.append(f"{path} {width_map[size_name]}w")
        
        return ", ".join(srcset_parts)
    
    @staticmethod
    def compress_image(image_file, max_width=1200, quality=85):
        """Compress image while maintaining aspect ratio"""
        try:
            img = Image.open(image_file)
            
            if img.width > max_width:
                ratio = max_width / img.width
                height = int(img.height * ratio)
                img = img.resize((max_width, height), Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            output.seek(0)
            return output
        except Exception as e:
            print(f"Image compression failed: {e}")
            return None
