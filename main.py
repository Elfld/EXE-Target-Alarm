"""
게임 시간 알림 프로그램 - Ultra-Minimalist Edition
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
    from winotify import Notification
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False


# ========================================
# 디자인 시스템 (Design Tokens)
# ========================================
class DesignSystem:
    """UI 일관성을 위한 디자인 변수 중앙 관리"""

    # 색상 팔레트
    BG_PRIMARY = "#FAFAFA"          # 메인 배경 (Warm White)
    TEXT_PRIMARY = "#2C2C2C"        # 주요 텍스트 (Dark Grey)
    TEXT_SECONDARY = "#999999"      # 보조 텍스트 (Light Grey)
    TEXT_ACCENT = "#333333"         # 강조 텍스트 (Very Dark Grey)

    BUTTON_PRIMARY = "#333333"      # 메인 버튼
    BUTTON_HOVER = "#1A1A1A"        # 버튼 호버
    BUTTON_SECONDARY = "#E8E8E8"    # 보조 버튼

    ACCENT_BLUE = "#4A90E2"         # 액센트 컬러

    # 상태 색상
    STATUS_WAITING = "#999999"      # 대기 중
    STATUS_SEARCHING = "#F39C12"    # 검색 중
    STATUS_ACTIVE = "#27AE60"       # 활성화
    STATUS_ERROR = "#E74C3C"        # 에러

    # 폰트
    FONT_FAMILY = "Segoe UI"
    FONT_TITLE = ("Segoe UI", 32, "bold")       # 타이틀
    FONT_TIME = ("Segoe UI", 28, "bold")        # 시간 선택 (큰 숫자)
    FONT_SENTENCE = ("Segoe UI", 18)            # 문장형 텍스트
    FONT_LABEL = ("Segoe UI", 14)               # 일반 라벨
    FONT_SMALL = ("Segoe UI", 12)               # 작은 텍스트
    FONT_STATUS = ("Segoe UI", 11)              # 상태바

    # 레이아웃
    WINDOW_WIDTH = 400
    WINDOW_HEIGHT = 380
    PADDING_LARGE = 30
    PADDING_MEDIUM = 20
    PADDING_SMALL = 10

    BUTTON_RADIUS = 25
    BUTTON_HEIGHT = 50


class GameAlarmApp:
    """게임 알림 애플리케이션 메인 클래스"""

    def __init__(self):
        # 디자인 시스템 참조
        self.ds = DesignSystem

        # 메인 윈도우 설정
        self.root = ctk.CTk()
        self.root.title("Game Alarm")
        self.root.geometry(f"{self.ds.WINDOW_WIDTH}x{self.ds.WINDOW_HEIGHT}")
        self.root.resizable(False, False)

        # 라이트 모드 설정
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # 배경색 설정
        self.root.configure(fg_color=self.ds.BG_PRIMARY)

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
        """Ultra-Minimalist UI 구성 - Text-Embedded Interaction"""

        # ========================================
        # 상단 여백
        # ========================================
        ctk.CTkLabel(
            self.root,
            text="",
            height=self.ds.PADDING_LARGE,
            fg_color="transparent"
        ).pack()

        # ========================================
        # 타이틀
        # ========================================
        title = ctk.CTkLabel(
            self.root,
            text="Game Alarm",
            font=self.ds.FONT_TITLE,
            text_color=self.ds.TEXT_PRIMARY,
            fg_color="transparent"
        )
        title.pack(pady=(0, self.ds.PADDING_LARGE))

        # ========================================
        # 타겟 프로세스 (Label + Change Button)
        # ========================================
        target_container = ctk.CTkFrame(self.root, fg_color="transparent")
        target_container.pack(pady=self.ds.PADDING_SMALL)

        self.target_label = ctk.CTkLabel(
            target_container,
            text="No game selected",
            font=self.ds.FONT_LABEL,
            text_color=self.ds.TEXT_SECONDARY,
            fg_color="transparent"
        )
        self.target_label.pack(side="left", padx=5)

        # Change 버튼 (투명한 텍스트 버튼)
        change_button = ctk.CTkButton(
            target_container,
            text="[Change]",
            command=self.browse_file,
            width=70,
            height=25,
            fg_color="transparent",
            hover_color=self.ds.BUTTON_SECONDARY,
            text_color=self.ds.ACCENT_BLUE,
            font=self.ds.FONT_SMALL,
            border_width=0
        )
        change_button.pack(side="left", padx=5)

        # ========================================
        # 문장형 시간 선택: "Every Hour at [ 02 ] min"
        # ========================================
        sentence_container = ctk.CTkFrame(self.root, fg_color="transparent")
        sentence_container.pack(pady=self.ds.PADDING_LARGE)

        # "Every Hour at" 텍스트
        ctk.CTkLabel(
            sentence_container,
            text="Every Hour at",
            font=self.ds.FONT_SENTENCE,
            text_color=self.ds.TEXT_PRIMARY,
            fg_color="transparent"
        ).pack(side="left", padx=(0, 8))

        # [ 02 ] - ComboBox (투명 스타일, 큰 폰트)
        # 00~59까지의 분 리스트 생성
        minutes = [f"{i:02d}" for i in range(60)]

        self.minute_combo = ctk.CTkComboBox(
            sentence_container,
            values=minutes,
            width=80,
            height=45,
            # 투명 스타일 (핵심!) - 배경색과 동일하게 설정
            fg_color=self.ds.BG_PRIMARY,      # 배경과 동일한 색 (시각적으로 투명)
            border_width=0,                   # 테두리 제거
            button_color=self.ds.BG_PRIMARY,  # 드롭다운 버튼 배경도 동일
            button_hover_color=self.ds.BUTTON_SECONDARY,
            dropdown_fg_color=self.ds.BG_PRIMARY,
            dropdown_hover_color=self.ds.BUTTON_SECONDARY,
            # 폰트 크게 (강조)
            font=self.ds.FONT_TIME,
            text_color=self.ds.TEXT_ACCENT,
            dropdown_font=self.ds.FONT_LABEL,
            # 상태
            state="readonly"
        )
        self.minute_combo.set("02")  # 기본값
        self.minute_combo.pack(side="left", padx=5)

        # "min" 텍스트
        ctk.CTkLabel(
            sentence_container,
            text="min",
            font=self.ds.FONT_SENTENCE,
            text_color=self.ds.TEXT_PRIMARY,
            fg_color="transparent"
        ).pack(side="left", padx=(8, 0))

        # ========================================
        # 사운드 토글 (작은 체크박스 스타일)
        # ========================================
        sound_container = ctk.CTkFrame(self.root, fg_color="transparent")
        sound_container.pack(pady=self.ds.PADDING_MEDIUM)

        self.sound_checkbox = ctk.CTkCheckBox(
            sound_container,
            text="Enable Sound Alert",
            font=self.ds.FONT_SMALL,
            text_color=self.ds.TEXT_SECONDARY,
            fg_color=self.ds.ACCENT_BLUE,
            hover_color=self.ds.BUTTON_HOVER,
            border_width=1
        )
        self.sound_checkbox.select()  # 기본값: ON
        self.sound_checkbox.pack()

        # ========================================
        # 메인 버튼 (Start / Stop)
        # ========================================
        button_container = ctk.CTkFrame(self.root, fg_color="transparent")
        button_container.pack(pady=self.ds.PADDING_LARGE)

        self.main_button = ctk.CTkButton(
            button_container,
            text="Start Monitoring",
            command=self.toggle_monitoring,
            width=280,
            height=self.ds.BUTTON_HEIGHT,
            corner_radius=self.ds.BUTTON_RADIUS,
            fg_color=self.ds.BUTTON_PRIMARY,
            hover_color=self.ds.BUTTON_HOVER,
            text_color="#FFFFFF",
            font=self.ds.FONT_LABEL
        )
        self.main_button.pack()

        # ========================================
        # 하단 상태 표시 (Status Bar)
        # ========================================
        # 윈도우 하단에 고정
        self.status_bar = ctk.CTkLabel(
            self.root,
            text="⚫ Waiting for Start",
            font=self.ds.FONT_STATUS,
            text_color=self.ds.STATUS_WAITING,
            fg_color="transparent",
            anchor="center"
        )
        self.status_bar.pack(side="bottom", pady=self.ds.PADDING_SMALL)

    def browse_file(self):
        """타겟 프로세스 선택"""
        file_path = filedialog.askopenfilename(
            title="Select Target Game Process",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )

        if file_path:
            file_name = os.path.basename(file_path)
            self.target_process = file_name
            # UI 업데이트
            self.target_label.configure(
                text=file_name,
                text_color=self.ds.TEXT_ACCENT
            )

    def toggle_monitoring(self):
        """감시 시작/중지 토글"""
        if self.monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self):
        """감시 시작"""
        # 입력값 검증: 타겟 프로세스
        if not self.target_process:
            self.status_bar.configure(
                text="⚠️ Please select a game first",
                text_color=self.ds.STATUS_ERROR
            )
            return

        # 입력값 검증: 알림 분
        try:
            self.alert_minute = int(self.minute_combo.get())
        except ValueError:
            self.status_bar.configure(
                text="⚠️ Invalid minute",
                text_color=self.ds.STATUS_ERROR
            )
            return

        # 사운드 설정
        self.sound_enabled = self.sound_checkbox.get()

        # 설정 저장
        self.save_config()

        # 감시 시작
        self.monitoring = True
        self.last_alerted_hour = -1

        # UI 업데이트
        self.main_button.configure(
            text="Stop Monitoring",
            fg_color=self.ds.STATUS_ERROR,
            hover_color="#C0392B"
        )
        self.status_bar.configure(
            text="🟡 Searching for game...",
            text_color=self.ds.STATUS_SEARCHING
        )

        # 감시 스레드 시작
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """감시 중지"""
        self.monitoring = False

        # UI 업데이트
        self.main_button.configure(
            text="Start Monitoring",
            fg_color=self.ds.BUTTON_PRIMARY,
            hover_color=self.ds.BUTTON_HOVER
        )
        self.status_bar.configure(
            text="⚫ Waiting for Start",
            text_color=self.ds.STATUS_WAITING
        )

    def monitor_loop(self):
        """메인 감시 루프 - 프로세스 감지 및 시간 체크"""
        game_found = False

        while self.monitoring:
            try:
                now = datetime.now()
                current_minute = now.minute
                current_hour = now.hour

                # 프로세스 실행 여부 확인
                is_running = self.is_process_running(self.target_process)

                # 상태바 업데이트 (게임 발견 시)
                if is_running and not game_found:
                    game_found = True
                    self.update_status(
                        f"🟢 Game Found! Alarm at :{self.alert_minute:02d}",
                        self.ds.STATUS_ACTIVE
                    )
                elif not is_running and game_found:
                    game_found = False
                    self.update_status(
                        "🟡 Searching for game...",
                        self.ds.STATUS_SEARCHING
                    )

                # 알림 조건 체크
                if current_minute == self.alert_minute:
                    if self.last_alerted_hour != current_hour:
                        if is_running:
                            self.send_alert(now)
                            self.last_alerted_hour = current_hour

                time.sleep(1)

            except Exception:
                time.sleep(1)

    def update_status(self, text, color):
        """상태바 업데이트 (메인 스레드에서 실행)"""
        self.root.after(0, lambda: self.status_bar.configure(
            text=text,
            text_color=color
        ))

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
                self.target_label.configure(
                    text=self.target_process,
                    text_color=self.ds.TEXT_ACCENT
                )

            # 분 설정
            self.minute_combo.set(f"{self.alert_minute:02d}")

            # 사운드 설정
            if self.sound_enabled:
                self.sound_checkbox.select()
            else:
                self.sound_checkbox.deselect()

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
