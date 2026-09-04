"""QR codes as inline SVG, so labels print crisply at any size."""
import qrcode
import qrcode.image.svg


def svg(data):
    img = qrcode.make(
        data,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=10,
        border=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
    )
    return img.to_string(encoding="unicode")
