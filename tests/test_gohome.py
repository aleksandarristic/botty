from botty.gohome import format_network_tests


def test_format_network_tests_full_payload():
    payload = {
        "speedtest": {
            "Available": True,
            "DownloadMbps": 491.17468,
            "UploadMbps": 235.042288,
            "PingMs": 2.217,
            "LastUpdatedText": "1h ago",
            "NextScheduledISO": "2026-02-02T12:19:56+01:00",
        },
        "ping": {
            "Available": True,
            "Targets": [
                {"Name": "Cloudflare DNS", "AvgMs": 3.625, "PacketLoss": 0},
                {"Name": "Quad9", "AvgMs": 4.457, "PacketLoss": 0},
            ],
        },
        "device": {
            "Available": True,
            "TemperatureC": 61.8,
            "UptimeText": "2d 1h 50m",
            "MemoryUsedMB": 1024.0,
            "MemoryTotalMB": 2048.0,
            "Load1": 0.06,
            "Load5": 0.02,
            "Load15": 0.01,
        },
    }

    message = format_network_tests(payload)

    assert "*Network Test Results*" in message
    assert "Download: 491.17 Mbps" in message
    assert "Updated:  1h ago" in message
    assert "Next Run: 2026-02-02T12:19:56+01:00" in message
    assert "Cloudflare DNS :   3.62 ms" in message
    assert "Memory:   1.00/2.00 GB used" in message
    assert "Loads:    0.06, 0.02, 0.01" in message
    assert "```" in message


def test_format_network_tests_missing_sections():
    payload = {
        "speedtest": {"Available": False},
        "ping": {"Available": False},
        "device": {"Available": False},
    }

    message = format_network_tests(payload)

    assert "Speedtest:" in message
    assert "No data available" in message
    assert "Ping:" in message
    assert "Device Metrics:" in message
