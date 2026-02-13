"""CDS HiPS image cutout URL builder.

Uses the HiPS2FITS REST API to build direct image URLs for surveys that
often fail or timeout with SkyView (2MASS-J, GALEX, DSS). No network call
here; we only build the URL. The orchestrator will GET it.
"""

from __future__ import annotations

import urllib.parse

HIPS2FITS_BASE = "https://alasky.cds.unistra.fr/hips-image-services/hips2fits"
DEFAULT_PIXELS = 300

# Survey name (as used in band mapping) -> CDS HiPS dataset ID or keyword
# GALEX: keyword "GALEX" (el path largo devolvía 400 Bad Request)
SURVEY_TO_HIPS: dict[str, str] = {
    "2MASS-J": "CDS/P/2MASS/J",
    "GALEX": "GALEX",
    "DSS": "CDS/P/DSS2/color",
}


def get_image_url(
    ra_deg: float,
    dec_deg: float,
    survey: str,
    size_arcmin: float = 10.0,
    pixels: int = DEFAULT_PIXELS,
) -> str:
    """Return HiPS2FITS JPEG URL for the given position and survey.

    Only supports surveys listed in SURVEY_TO_HIPS (2MASS-J, GALEX, DSS).
    Raises ValueError if survey is not supported.
    """
    hips_id = SURVEY_TO_HIPS.get(survey)
    if not hips_id:
        raise ValueError(
            f"HiPS does not support survey {survey!r}. "
            f"Supported: {list(SURVEY_TO_HIPS.keys())}"
        )
    fov_deg = size_arcmin / 60.0
    params = {
        "hips": hips_id,
        "width": pixels,
        "height": pixels,
        "projection": "SIN",
        "fov": round(fov_deg, 6),
        "ra": round(ra_deg, 6),
        "dec": round(dec_deg, 6),
        "format": "jpg",
        "coordsys": "icrs",
    }
    return f"{HIPS2FITS_BASE}?{urllib.parse.urlencode(params)}"
