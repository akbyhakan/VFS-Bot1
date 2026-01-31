"""Dynamic User-Agent rotation for anti-detection."""

import random
from typing import List


class UserAgentRotator:
    """Dinamik User-Agent rotasyonu için sınıf."""

    CHROME_VERSIONS = ["120.0.0.0", "121.0.0.0", "122.0.0.0", "123.0.0.0", "124.0.0.0"]
    PLATFORMS = [
        "Windows NT 10.0; Win64; x64",
        "Windows NT 11.0; Win64; x64",
        "Macintosh; Intel Mac OS X 10_15_7",
        "Macintosh; Intel Mac OS X 14_0",
    ]

    @classmethod
    def get_random_user_agent(cls) -> str:
        """
        Rastgele bir User-Agent döndürür.

        Returns:
            Random User-Agent string
        """
        platform = random.choice(cls.PLATFORMS)
        chrome_version = random.choice(cls.CHROME_VERSIONS)

        return (
            f"Mozilla/5.0 ({platform}) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome_version} Safari/537.36"
        )

    @classmethod
    def get_user_agents_list(cls) -> List[str]:
        """
        Tüm olası User-Agent kombinasyonlarını döndürür.

        Returns:
            List of all possible User-Agent combinations
        """
        agents = []
        for platform in cls.PLATFORMS:
            for version in cls.CHROME_VERSIONS:
                agents.append(
                    f"Mozilla/5.0 ({platform}) "
                    f"AppleWebKit/537.36 (KHTML, like Gecko) "
                    f"Chrome/{version} Safari/537.36"
                )
        return agents
