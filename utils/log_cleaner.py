"""
로그 자동 정리 - 오래된 로그 파일 삭제

지정한 보관 기간(기본 30일)이 지난 로그 파일을 삭제한다.
프로그램 시작 시 1회 호출하면 디스크가 가득 차는 것을 방지한다.
"""
import os
import time
from utils.logger import get_logger
from config.settings import LOG_DIR

logger = get_logger(__name__)


def clean_old_logs(log_dir=None, keep_days=30):
    """keep_days 보다 오래된 로그 파일 삭제. 삭제한 파일 수 반환."""
    log_dir = log_dir or LOG_DIR
    if not os.path.isdir(log_dir):
        return 0

    cutoff = time.time() - keep_days * 86400
    removed = 0
    for fname in os.listdir(log_dir):
        fpath = os.path.join(log_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            if os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
                removed += 1
                logger.info(f"오래된 로그 삭제: {fname}")
        except OSError as e:
            logger.warning(f"로그 삭제 실패 {fname}: {e}")

    if removed:
        logger.info(f"로그 정리 완료: {removed}개 삭제 (보관 {keep_days}일)")
    return removed
