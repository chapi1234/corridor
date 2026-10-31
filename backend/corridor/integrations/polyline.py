"""Google encoded polyline format (https://developers.google.com/maps/documentation/utilities/polylinealgorithm).

OSRM's ``polyline6`` uses the same algorithm with six decimal places of precision.
"""

from __future__ import annotations

from collections.abc import Iterable

from corridor.domain.geometry import LatLon


def decode(encoded: str, precision: int = 6) -> list[LatLon]:
    factor = 10**precision
    points: list[LatLon] = []
    index = lat = lon = 0
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        points.append(LatLon(lat / factor, lon / factor))
    return points


def encode(points: Iterable[LatLon], precision: int = 6) -> str:
    factor = 10**precision
    chunks: list[str] = []
    prev_lat = prev_lon = 0
    for point in points:
        lat, lon = round(point.lat * factor), round(point.lon * factor)
        for delta in (lat - prev_lat, lon - prev_lon):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                chunks.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            chunks.append(chr(value + 63))
        prev_lat, prev_lon = lat, lon
    return "".join(chunks)
