import logging
import struct
import zlib
import json

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)


class RawToJson:
    def __init__(self, hass):
        self.hass = hass
        self._jdata = None

    @callback
    def extract_png_chunks(self, data):
        # Used for fast-ish conversion between uint8s and uint32s/int32s.
        # Also required in order to remain agnostic for both Python bytes
        # and memory view objects.
        uint8 = bytearray(4)
        uint32 = struct.Struct(">I")

        if data[0] != 0x89:
            raise Warning("Invalid .png file header")
        elif data[1] != 0x50:
            raise Warning("Invalid .png file header")
        elif data[2] != 0x4E:
            raise Warning("Invalid .png file header")
        elif data[3] != 0x47:
            raise Warning("Invalid .png file header")
        elif data[4] != 0x0D:
            raise Warning(
                "Invalid .png file header: possibly caused by DOS-Unix line ending conversion?"
            )
        elif data[5] != 0x0A:
            raise Warning(
                "Invalid .png file header: possibly caused by DOS-Unix line ending conversion?"
            )
        elif data[6] != 0x1A:
            raise Warning("Invalid .png file header")
        elif data[7] != 0x0A:
            raise Warning(
                "Invalid .png file header: possibly caused by DOS-Unix line ending conversion?"
            )
        else:
            ended = False
            idx = 8

            while idx < len(data):
                # Read the length of the current chunk,
                # which is stored as an Uint32.

                uint8[0], uint8[1], uint8[2], uint8[3] = data[idx: idx + 4]
                idx += 4

                # Chunk includes name/type for CRC check (see below).
                length = uint32.unpack(uint8)[0] + 4

                chunk = bytearray(length)

                chunk[0:4] = data[idx: idx + 4]
                idx += 4

                # Get the name in ASCII for identification.
                name = chunk[0:4].decode("ascii")

                # The IEND header marks the end of the file,
                # so on discovering it break out of the loop.
                if name == "IEND":
                    _LOGGER.debug("PNG file read end")
                    ended = True
                    return ended

                # Read the contents of the chunk out of the main buffer.
                chunk[4:length] = data[idx: idx + length - 4]
                idx += length - 4

                # Skip the CRC32
                idx += 4

                # The chunk data is now copied to remove the 4 preceding
                # bytes used for the chunk name/type.
                chunk_data = memoryview(chunk)[4:]

                if name == "zTXt":
                    i = 0
                    keyword = ""

                    while chunk_data[i] != 0 and i < 79:
                        keyword += chr(chunk_data[i])
                        i += 1

                    i += 2

                    self._jdata = chunk_data[i:length].tobytes()
                    del data
                    _LOGGER.debug("Valetudo Json data grabbed")
                    return self._jdata

    def camera_message_received(self, payload):
        # Process the camera data here
        _LOGGER.debug("Decoding PNG to JSON")
        if payload is not None:
            try:
                extract_data = self.extract_png_chunks(payload)
            except Warning as warning:
                _LOGGER.warning("MQTT message format error:", {warning})
                return None
            else:
                if (self._jdata != None) or (extract_data != None):
                    _LOGGER.debug("Extracting JSON")
                    dec_data = zlib.decompress(self._jdata).decode("utf-8")
                    json_data = dec_data
                    response = json.loads(json_data)
                    _LOGGER.debug("Extracting JSON Complete")
                    del json_data
                    return response
        else:
            _LOGGER.debug("No data to process")
            return None
