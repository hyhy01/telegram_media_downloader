"""Downloads media from telegram."""
import asyncio
import logging
import os
from typing import List, Optional, Tuple, Union
import time
import pyrogram
import yaml
from pyrogram.types import Audio, Document, Photo, Video, VideoNote, Voice
from rich.logging import RichHandler

from utils.file_management import get_next_name, manage_duplicate_file
from utils.log import LogFilter
from utils.meta import print_meta
from utils.updates import check_for_updates

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()],
)
logging.getLogger("pyrogram.session.session").addFilter(LogFilter())
logging.getLogger("pyrogram.client").addFilter(LogFilter())
logger = logging.getLogger("media_downloader")

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
FAILED_IDS: list = []
DOWNLOADED_IDS: list = []
IDS_TO_SKIP: set = set([])


def update_config(config: dict):
    """
    Update existing configuration file.

    Parameters
    ----------
    config: dict
        Configuration to be written into config file.
    """
    config["ids_to_retry"] = (
        list((set(config["ids_to_retry"]) - set(DOWNLOADED_IDS)) |  set(FAILED_IDS))
    )
    config["ids_to_skip"] = (
        list(IDS_TO_SKIP | set(DOWNLOADED_IDS))
    )
    with open("config.yaml", "w") as yaml_file:
        yaml.dump(config, yaml_file, default_flow_style=False)
    logger.info("Updated last read message_id to config file")


def _can_download(_type: str, file_formats: dict, file_format: Optional[str]) -> bool:
    """
    Check if the given file format can be downloaded.

    Parameters
    ----------
    _type: str
        Type of media object.
    file_formats: dict
        Dictionary containing the list of file_formats
        to be downloaded for `audio`, `document` & `video`
        media types
    file_format: str
        Format of the current file to be downloaded.

    Returns
    -------
    bool
        True if the file format can be downloaded else False.
    """
    if _type in ["audio", "document", "video"]:
        allowed_formats: list = file_formats[_type]
        if not file_format in allowed_formats and allowed_formats[0] != "all":
            return False
    return True


def _is_exist(file_path: str) -> bool:
    """
    Check if a file exists and it is not a directory.

    Parameters
    ----------
    file_path: str
        Absolute path of the file to be checked.

    Returns
    -------
    bool
        True if the file exists else False.
    """
    return not os.path.isdir(file_path) and os.path.exists(file_path)


async def _get_media_meta(
    media_obj: Union[Audio, Document, Photo, Video, VideoNote, Voice],
    _type: str,
) -> Tuple[str, Optional[str]]:
    """Extract file name and file id from media object.

    Parameters
    ----------
    media_obj: Union[Audio, Document, Photo, Video, VideoNote, Voice]
        Media object to be extracted.
    _type: str
        Type of media object.

    Returns
    -------
    Tuple[str, Optional[str]]
        file_name, file_format
    """
    if _type in ["audio", "document", "video"]:
        # pylint: disable = C0301
        file_format: Optional[str] = media_obj.mime_type.split("/")[-1]  # type: ignore
    else:
        file_format = None

    if _type in ["voice", "video_note"]:
        # pylint: disable = C0209
        file_format = media_obj.mime_type.split("/")[-1]  # type: ignore
        file_name: str = os.path.join(
            THIS_DIR,
            _type,
            "{}_{}.{}".format(
                _type,
                media_obj.date.isoformat(),  # type: ignore
                file_format,
            ),
        )
    else:
        file_name = os.path.join(
            THIS_DIR, _type, getattr(media_obj, "file_name", None) or ""
        )
    return file_name, file_format


async def download_media(
    client: pyrogram.client.Client,
    message: pyrogram.types.Message,
    media_types: List[str],
    file_formats: dict,
):
    """
    Download media from Telegram.

    Each of the files to download are retried 3 times with a
    delay of 5 seconds each.

    Parameters
    ----------
    client: pyrogram.client.Client
        Client to interact with Telegram APIs.
    message: pyrogram.types.Message
        Message object retrieved from telegram.
    media_types: list
        List of strings of media types to be downloaded.
        Ex : `["audio", "photo"]`
        Supported formats:
            * audio
            * document
            * photo
            * video
            * voice
    file_formats: dict
        Dictionary containing the list of file_formats
        to be downloaded for `audio`, `document` & `video`
        media types.

    Returns
    -------
    int
        Current message id.
    """
    if message.id in IDS_TO_SKIP:
    	DOWNLOADED_IDS.append(message.id)
    	return message.id
    #print("sleep10")
    #time.sleep(10)
    await asyncio.sleep(10)
    #print("sleep10 end")
    for retry in range(3):
        try:
            if message.media is None:
                return message.id
            for _type in media_types:
                _media = getattr(message, _type, None)
                if _media is None:
                    continue
                file_name, file_format = await _get_media_meta(_media, _type)
                if _can_download(_type, file_formats, file_format):
                    if "." not in file_name:
                        (path, basename) = os.path.split(file_name)
                        file_name = '{}/##{}##{}.{}'.format(path, message.id,basename, file_format)
                    else:
                        (path, basename) = os.path.split(file_name)
                        file_name = '{}/##{}##{}'.format(path, message.id,basename)
                    if _is_exist(file_name):
                        file_name = get_next_name(file_name)
                        download_path = await client.download_media(
                            message, file_name=file_name
                        )
                        # pylint: disable = C0301
                        download_path = manage_duplicate_file(download_path)  # type: ignore
                    else:
                        download_path = await client.download_media(
                            message, file_name=file_name
                        )
                    file_size_total = 0
                    if message.video and _type=="video":
                    	file_size_total = message.video.file_size
                    if message.voice and _type=="voice":
                    	file_size_total = message.voice.file_size
                    if message.video_note and _type=="video_note":
                    	file_size_total = message.video_note.file_size
                    if message.photo and _type=="photo":
                    	file_size_total = message.photo.file_size
                    if message.sticker and _type=="sticker":
                    	file_size_total = message.sticker.file_size
                    if message.audio and _type=="audio":
                    	file_size_total = message.audio.file_size
                    if message.document and _type=="document":
                    	file_size_total = message.document.file_size
                    if message.animation and _type=="animation":
                    	file_size_total = message.animation.file_size
                    downloaded_size = os.path.getsize(download_path)
                    print("id:",message.id, download_path,downloaded_size , file_size_total)
                    if file_size_total != 0 and downloaded_size < file_size_total:
                    	raise Exception("downloaded partly!", download_path,message.id)
                    if downloaded_size > 0:
                        DOWNLOADED_IDS.append(message.id)
                        IDS_TO_SKIP.add(message.id)
                        if download_path:
                            logger.info("Media downloaded - %s", download_path)
                    else:
                    	raise Exception("size zero!", download_path,message.id)
            break
        except pyrogram.errors.exceptions.bad_request_400.BadRequest:
            logger.warning(
                "Message[%d]: file reference expired, refetching...",
                message.id,
            )
            message = await client.get_messages(  # type: ignore
                chat_id=message.chat.id,  # type: ignore
                message_ids=message.id,
            )
            if retry == 2:
                # pylint: disable = C0301
                logger.error(
                    "Message[%d]: file reference expired for 3 retries, download skipped.",
                    message.id,
                )
                FAILED_IDS.append(message.id)
        except TypeError:
            # pylint: disable = C0301
            logger.warning(
                "Timeout Error occurred when downloading Message[%d], retrying after 5 seconds",
                message.id,
            )
            await asyncio.sleep(5)
            if retry == 2:
                logger.error(
                    "Message[%d]: Timing out after 3 reties, download skipped.",
                    message.id,
                )
                FAILED_IDS.append(message.id)
        except Exception as e:
            # pylint: disable = C0301
            logger.error(
                "Message[%d]: could not be downloaded due to following exception:\n[%s].",
                message.id,
                e,
                exc_info=True,
            )
            FAILED_IDS.append(message.id)
            break
    return message.id


async def process_messages(
    client: pyrogram.client.Client,
    messages: List[pyrogram.types.Message],
    media_types: List[str],
    file_formats: dict,
) -> int:
    """
    Download media from Telegram.

    Parameters
    ----------
    client: pyrogram.client.Client
        Client to interact with Telegram APIs.
    messages: list
        List of telegram messages.
    media_types: list
        List of strings of media types to be downloaded.
        Ex : `["audio", "photo"]`
        Supported formats:
            * audio
            * document
            * photo
            * video
            * voice
    file_formats: dict
        Dictionary containing the list of file_formats
        to be downloaded for `audio`, `document` & `video`
        media types.

    Returns
    -------
    int
        Max value of list of message ids.
    """
    message_ids = [
            await download_media(client, message, media_types, file_formats)
            for message in messages
        ]
    #message_ids = await asyncio.gather(
    #    *[
    #        download_media(client, message, media_types, file_formats)
    #        for message in messages
    #    ]
    #)

    last_message_id: int = max(message_ids)
    return last_message_id


async def begin_import(config: dict, pagination_limit: int) -> dict:
    """
    Create pyrogram client and initiate download.

    The pyrogram client is created using the ``api_id``, ``api_hash``
    from the config and iter through message offset on the
    ``last_message_id`` and the requested file_formats.

    Parameters
    ----------
    config: dict
        Dict containing the config to create pyrogram client.
    pagination_limit: int
        Number of message to download asynchronously as a batch.

    Returns
    -------
    dict
        Updated configuration to be written into config file.
    """
    client = pyrogram.Client(
        "media_downloader",
        api_id=config["api_id"],
        api_hash=config["api_hash"],
        proxy=config.get("proxy"),
    )
    await client.start()
    last_read_message_id: int = config["last_read_message_id"]
    messages_iter = client.get_chat_history(
        config["chat_id"], offset_id=last_read_message_id, reverse=True
    )
    messages_list: list = []
    pagination_count: int = 0
    if config["ids_to_retry"]:
        logger.info("Downloading files failed during last run...")
        skipped_messages: list = await client.get_messages(  # type: ignore
            chat_id=config["chat_id"], message_ids=config["ids_to_retry"]
        )
        for message in skipped_messages:
            pagination_count += 1
            messages_list.append(message)
    if config["ids_to_skip"]:
    	IDS_TO_SKIP.update(config["ids_to_skip"])
    #async for message in messages_iter:  # type: ignore
    async for message in messages_iter: 
        if pagination_count < pagination_limit:
            pagination_count += 1
            messages_list.append(message)
        else:
            last_read_message_id = await process_messages(
                client,
                messages_list,
                config["media_types"],
                config["file_formats"],
            )
            pagination_count = 0
            messages_list = []
            messages_list.append(message)
            config["last_read_message_id"] = last_read_message_id
            update_config(config)
    if messages_list:
        last_read_message_id = await process_messages(
            client,
            messages_list,
            config["media_types"],
            config["file_formats"],
        )

    await client.stop()
    config["last_read_message_id"] = last_read_message_id
    return config


def main():
    """Main function of the downloader."""
    with open(os.path.join(THIS_DIR, "config.yaml")) as f:
        config = yaml.safe_load(f)
    updated_config = asyncio.get_event_loop().run_until_complete(
        begin_import(config, pagination_limit=3)
    )
    if FAILED_IDS:
        logger.info(
            "Downloading of %d files failed. "
            "Failed message ids are added to config file.\n"
            "These files will be downloaded on the next run.",
            len(set(FAILED_IDS)),
        )
    update_config(updated_config)
    check_for_updates()


if __name__ == "__main__":
    print_meta(logger)
    main()
