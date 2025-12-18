"""
게임 시간 알림 프로그램 - 미니멀 에디션
특정 게임(프로세스)이 실행 중일 때 매 시간 특정 분에 알림을 보냅니다.
"""

import customtkinter as ctk
from tkinter import filedialog
import threading
import time
import json
import os
from datetime import datetime
from pathlib import Path
import psutil

# Windows 전용 라이브러리
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False

# Toast 알림 (winotify - Windows 11 최적화)
try:
    from winotify import Notification, audio
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False


class GameAlarmApp:
    """게임 알림 애플리케이션 메인 클래스"""

    def __init__(self):
        # 메인 윈도우 설정
        self.root = ctk.CTk()
        self.root.title("Game Alarm")
        self.root.geometry("420x280")
        self.root.resizable(False, False)

        # 라이트 모드 설정 (아이보리/화이트)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # 설정 파일 경로
        self.config_file = Path("config.json")

        # 변수 초기화
        self.target_process = ""
        self.alert_minute = 2
        self.sound_enabled = True
        self.monitoring = False
        self.monitor_thread = None
        self.last_alerted_hour = -1

        # GUI 구성
        self.setup_ui()

        # 설정 불러오기
        self.load_config()

        # 윈도우 닫기 이벤트 처리
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        """미니멀 모던 UI 구성"""
        # 배경 색상 설정
        self.root.configure(fg_color="#FAF9F6")

        # 상단 여백
        ctk.CTkLabel(self.root, text="", height=20, fg_color="transparent").pack()

        # 타이틀
        title = ctk.CTkLabel(
            self.root,
            text="Game Alarm",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#2C2C2C"
        )
        title.pack(pady=(0, 25))

        # === 타겟 프로세스 ===
        process_container = ctk.CTkFrame(self.root, fg_color="transparent")
        process_container.pack(pady=8)

        ctk.CTkLabel(
            process_container,
            text="Target Process",
            font=ctk.CTkFont(size=13),
            text_color="#6B6B6B",
            width=120,
            anchor="w"
        ).pack(side="left", padx=(0, 10))

        self.process_entry = ctk.CTkEntry(
            process_container,
            placeholder_text="Select .exe file...",
            width=180,
            height=32,
            border_width=1,
            corner_radius=6
        )
        self.process_entry.pack(side="left", padx=5)

        ctk.CTkButton(
            process_container,
            text="📁",
            command=self.browse_file,
            width=40,
            height=32,
            corner_radius=6,
            fg_color="#4A90E2",
            hover_color="#3A7BC8"
        ).pack(side="left")

        # === 알림 분 ===
        minute_container = ctk.CTkFrame(self.root, fg_color="transparent")
        minute_container.pack(pady=8)

        ctk.CTkLabel(
            minute_container,
            text="Alert Minute",
            font=ctk.CTkFont(size=13),
            text_color="#6B6B6B",
            width=120,
            anchor="w"
        ).pack(side="left", padx=(0, 10))

        self.minute_entry = ctk.CTkEntry(
            minute_container,
            placeholder_text="0-59",
            width=80,
            height=32,
            border_width=1,
            corner_radius=6,
            justify="center"
        )
        self.minute_entry.pack(side="left", padx=5)
        self.minute_entry.insert(0, "2")

        ctk.CTkLabel(
            minute_container,
            text="Every hour at XX:02",
            font=ctk.CTkFont(size=11),
            text_color="#999999"
        ).pack(side="left", padx=10)

        # === 제어 버튼 영역 ===
        control_container = ctk.CTkFrame(self.root, fg_color="transparent")
        control_container.pack(pady=25)

        # 시작/중지 토글 버튼
        self.toggle_button = ctk.CTkButton(
            control_container,
            text="▶",
            command=self.toggle_monitoring,
            width=60,
            height=60,
            corner_radius=30,
            font=ctk.CTkFont(size=24),
            fg_color="#4A90E2",
            hover_color="#3A7BC8"
        )
        self.toggle_button.pack(side="left", padx=15)

        # 사운드 토글 버튼
        self.sound_button = ctk.CTkButton(
            control_container,
            text="🔊",
            command=self.toggle_sound,
            width=60,
            height=60,
            corner_radius=30,
            font=ctk.CTkFont(size=24),
            fg_color="#4A90E2",
            hover_color="#3A7BC8"
        )
        self.sound_button.pack(side="left", padx=15)

        # === 상태 표시 ===
        self.status_label = ctk.CTkLabel(
            self.root,
            text="Ready",
            font=ctk.CTkFont(size=13),
            text_color="#999999"
        )
        self.status_label.pack(pady=(10, 0))

    def browse_file(self):
        """파일 찾아보기"""
        file_path = filedialog.askopenfilename(
            title="Select Target Process",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")]
        )

        if file_path:
            file_name = os.path.basename(file_path)
            self.target_process = file_name
            self.process_entry.delete(0, "end")
            self.process_entry.insert(0, file_name)

    def toggle_sound(self):
        """사운드 토글"""
        self.sound_enabled = not self.sound_enabled
        self.sound_button.configure(text="🔊" if self.sound_enabled else "🔇")

    def toggle_monitoring(self):
        """감시 토글 (시작/중지)"""
        if self.monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self):
        """감시 시작"""
        # 입력값 검증
        if not self.process_entry.get().strip():
            self.status_label.configure(text="Please select a process", text_color="#E74C3C")
            return

        try:
            minute = int(self.minute_entry.get())
            if minute < 0 or minute > 59:
                raise ValueError()
            self.alert_minute = minute
        except ValueError:
            self.status_label.configure(text="Invalid minute (0-59)", text_color="#E74C3C")
            return

        self.target_process = self.process_entry.get().strip()

        # 설정 저장
        self.save_config()

        # 감시 시작
        self.monitoring = True
        self.last_alerted_hour = -1

        # UI 업데이트
        self.toggle_button.configure(text="⏸", fg_color="#E74C3C", hover_color="#C0392B")
        self.status_label.configure(text="Monitoring...", text_color="#27AE60")

        # 감시 스레드 시작
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """감시 중지"""
        self.monitoring = False

        # UI 업데이트
        self.toggle_button.configure(text="▶", fg_color="#4A90E2", hover_color="#3A7BC8")
        self.status_label.configure(text="Stopped", text_color="#999999")

    def monitor_loop(self):
        """메인 감시 루프"""
        while self.monitoring:
            try:
                now = datetime.now()
                current_minute = now.minute
                current_hour = now.hour

                # 조건 체크: 현재 분 == 알림 분 && 이번 시간 알림 안보냄 && 프로세스 실행 중
                if current_minute == self.alert_minute:
                    if self.last_alerted_hour != current_hour:
                        if self.is_process_running(self.target_process):
                            self.send_alert(now)
                            self.last_alerted_hour = current_hour

                time.sleep(1)

            except Exception:
                time.sleep(1)

    def is_process_running(self, process_name):
        """프로세스 실행 여부 확인"""
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'].lower() == process_name.lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            return False
        except Exception:
            return False

    def send_alert(self, current_time):
        """알림 발송 (Toast + 사운드)"""
        time_str = current_time.strftime("%H:%M")
        message = f"{time_str} - {self.target_process} is running!"

        # Toast 알림 (winotify)
        if TOAST_AVAILABLE:
            try:
                toast = Notification(
                    app_id="Game Alarm",
                    title="Game Time Alert",
                    msg=message,
                    duration="short"
                )
                threading.Thread(target=toast.show, daemon=True).start()
            except Exception:
                pass

        # 사운드 알림
        if self.sound_enabled and WINSOUND_AVAILABLE:
            try:
                threading.Thread(
                    target=lambda: winsound.MessageBeep(winsound.MB_ICONASTERISK),
                    daemon=True
                ).start()
            except Exception:
                pass

    def save_config(self):
        """설정 저장"""
        config = {
            "target_process": self.target_process,
            "alert_minute": self.alert_minute,
            "sound_enabled": self.sound_enabled
        }

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def load_config(self):
        """설정 불러오기"""
        if not self.config_file.exists():
            return

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 설정 적용
            self.target_process = config.get("target_process", "")
            self.alert_minute = config.get("alert_minute", 2)
            self.sound_enabled = config.get("sound_enabled", True)

            # UI 업데이트
            if self.target_process:
                self.process_entry.delete(0, "end")
                self.process_entry.insert(0, self.target_process)

            self.minute_entry.delete(0, "end")
            self.minute_entry.insert(0, str(self.alert_minute))

            self.sound_button.configure(text="🔊" if self.sound_enabled else "🔇")

        except Exception:
            pass

    def on_closing(self):
        """프로그램 종료 처리"""
        # 감시 중지
        self.monitoring = False

        # 설정 저장
        if self.target_process:
            self.save_config()

        # 윈도우 닫기
        self.root.destroy()

    def run(self):
        """애플리케이션 실행"""
        self.root.mainloop()


def main():
    """메인 함수"""
    app = GameAlarmApp()
    app.run()


if __name__ == "__main__":
    main()
