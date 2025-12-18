"""
게임 시간 알림 프로그램
특정 게임(프로세스)이 실행 중일 때 매 시간 특정 분에 알림을 보냅니다.
"""

import customtkinter as ctk
from tkinter import filedialog, scrolledtext
import threading
import time
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import psutil

# Windows 전용 라이브러리 (다른 OS에서는 대체)
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False

try:
    from win10toast_click import ToastNotifier
    TOAST_AVAILABLE = True
except ImportError:
    try:
        from plyer import notification
        TOAST_AVAILABLE = True
    except ImportError:
        TOAST_AVAILABLE = False


class GameAlarmApp:
    """게임 알림 애플리케이션 메인 클래스"""

    def __init__(self):
        # 메인 윈도우 설정
        self.root = ctk.CTk()
        self.root.title("게임 시간 알림기")
        self.root.geometry("650x600")

        # 다크 모드 설정
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 설정 파일 경로
        self.config_file = Path("config.json")

        # 변수 초기화
        self.target_process = ""  # 타겟 프로세스명 (예: "game.exe")
        self.alert_minute = 2  # 알림을 보낼 분 (0-59)
        self.sound_enabled = True  # 사운드 활성화 여부
        self.monitoring = False  # 감시 중 여부
        self.monitor_thread = None  # 감시 스레드
        self.last_alerted_hour = -1  # 마지막 알림 보낸 시간 (중복 방지)

        # 토스트 알림 초기화
        if TOAST_AVAILABLE:
            try:
                self.toaster = ToastNotifier()
            except:
                self.toaster = None
        else:
            self.toaster = None

        # GUI 구성
        self.setup_ui()

        # 설정 불러오기
        self.load_config()

        # 윈도우 닫기 이벤트 처리
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        """GUI 레이아웃 구성"""
        # 메인 프레임
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 제목
        title_label = ctk.CTkLabel(
            main_frame,
            text="🎮 게임 시간 알림기",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(10, 20))

        # 설정 프레임
        settings_frame = ctk.CTkFrame(main_frame)
        settings_frame.pack(fill="x", padx=10, pady=5)

        # 1. 타겟 프로세스 선택
        process_frame = ctk.CTkFrame(settings_frame)
        process_frame.pack(fill="x", padx=10, pady=10)

        process_label = ctk.CTkLabel(
            process_frame,
            text="타겟 프로세스:",
            font=ctk.CTkFont(size=14)
        )
        process_label.pack(side="left", padx=5)

        self.process_entry = ctk.CTkEntry(
            process_frame,
            placeholder_text="exe 파일을 선택하세요...",
            width=300
        )
        self.process_entry.pack(side="left", padx=5)

        browse_button = ctk.CTkButton(
            process_frame,
            text="찾아보기",
            command=self.browse_file,
            width=100
        )
        browse_button.pack(side="left", padx=5)

        # 2. 알림 분 설정
        minute_frame = ctk.CTkFrame(settings_frame)
        minute_frame.pack(fill="x", padx=10, pady=10)

        minute_label = ctk.CTkLabel(
            minute_frame,
            text="알림 분 (0-59):",
            font=ctk.CTkFont(size=14)
        )
        minute_label.pack(side="left", padx=5)

        self.minute_entry = ctk.CTkEntry(
            minute_frame,
            placeholder_text="2",
            width=100
        )
        self.minute_entry.pack(side="left", padx=5)
        self.minute_entry.insert(0, "2")

        minute_help = ctk.CTkLabel(
            minute_frame,
            text="예: 2분 입력 시 매 시간 XX:02에 알림",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        minute_help.pack(side="left", padx=10)

        # 3. 사운드 설정
        sound_frame = ctk.CTkFrame(settings_frame)
        sound_frame.pack(fill="x", padx=10, pady=10)

        sound_label = ctk.CTkLabel(
            sound_frame,
            text="사운드 알림:",
            font=ctk.CTkFont(size=14)
        )
        sound_label.pack(side="left", padx=5)

        self.sound_switch = ctk.CTkSwitch(
            sound_frame,
            text="사운드 켜기",
            command=self.toggle_sound
        )
        self.sound_switch.pack(side="left", padx=5)
        self.sound_switch.select()  # 기본값: ON

        # 제어 버튼 프레임
        control_frame = ctk.CTkFrame(main_frame)
        control_frame.pack(fill="x", padx=10, pady=10)

        self.start_button = ctk.CTkButton(
            control_frame,
            text="감시 시작",
            command=self.start_monitoring,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=40,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.start_button.pack(side="left", expand=True, fill="x", padx=5)

        self.stop_button = ctk.CTkButton(
            control_frame,
            text="감시 중지",
            command=self.stop_monitoring,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=40,
            fg_color="red",
            hover_color="darkred",
            state="disabled"
        )
        self.stop_button.pack(side="left", expand=True, fill="x", padx=5)

        # 상태 표시
        self.status_label = ctk.CTkLabel(
            main_frame,
            text="⚪ 중지됨",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.status_label.pack(pady=5)

        # 로그 프레임
        log_frame = ctk.CTkFrame(main_frame)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        log_title = ctk.CTkLabel(
            log_frame,
            text="📋 로그",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        log_title.pack(pady=5)

        # 로그 텍스트 영역 (Tkinter의 ScrolledText 사용)
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap="word",
            height=12,
            bg="#2b2b2b",
            fg="#ffffff",
            font=("Consolas", 10)
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        # 초기 로그 메시지
        self.add_log("프로그램이 시작되었습니다.")
        if not TOAST_AVAILABLE:
            self.add_log("⚠️ 경고: 알림 라이브러리가 없습니다. pip install win10toast-click 또는 plyer를 설치하세요.")
        if not WINSOUND_AVAILABLE:
            self.add_log("⚠️ 경고: winsound를 사용할 수 없습니다. (Windows 전용)")

    def browse_file(self):
        """파일 찾아보기 대화상자"""
        file_path = filedialog.askopenfilename(
            title="타겟 프로세스 선택",
            filetypes=[("실행 파일", "*.exe"), ("모든 파일", "*.*")]
        )

        if file_path:
            # 파일명만 추출 (경로 제외)
            file_name = os.path.basename(file_path)
            self.target_process = file_name
            self.process_entry.delete(0, "end")
            self.process_entry.insert(0, file_name)
            self.add_log(f"타겟 프로세스 설정: {file_name}")

    def toggle_sound(self):
        """사운드 토글"""
        self.sound_enabled = self.sound_switch.get()
        status = "켜짐" if self.sound_enabled else "꺼짐"
        self.add_log(f"사운드: {status}")

    def start_monitoring(self):
        """감시 시작"""
        # 입력값 검증
        if not self.process_entry.get():
            self.add_log("❌ 오류: 타겟 프로세스를 선택하세요!")
            return

        try:
            minute = int(self.minute_entry.get())
            if minute < 0 or minute > 59:
                raise ValueError("분은 0-59 사이여야 합니다.")
            self.alert_minute = minute
        except ValueError as e:
            self.add_log(f"❌ 오류: 유효한 분을 입력하세요 (0-59)")
            return

        self.target_process = self.process_entry.get()

        # 설정 저장
        self.save_config()

        # 감시 시작
        self.monitoring = True
        self.last_alerted_hour = -1  # 초기화

        # UI 업데이트
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_label.configure(text="🟢 감시 중", text_color="green")

        # 감시 스레드 시작
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        self.add_log(f"✅ 감시 시작: {self.target_process} | 알림 분: {self.alert_minute}분")

    def stop_monitoring(self):
        """감시 중지"""
        self.monitoring = False

        # UI 업데이트
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="⚪ 중지됨", text_color="gray")

        self.add_log("⏸️ 감시가 중지되었습니다.")

    def monitor_loop(self):
        """
        메인 감시 루프 (별도 스레드에서 실행)
        1초 간격으로 현재 시각과 프로세스를 확인하여 알림 조건을 체크
        """
        while self.monitoring:
            try:
                now = datetime.now()
                current_minute = now.minute
                current_hour = now.hour

                # 조건 1: 현재 분이 설정한 알림 분과 일치하는가?
                if current_minute == self.alert_minute:
                    # 조건 2: 이미 이번 시간에 알림을 보냈는가? (중복 방지)
                    if self.last_alerted_hour != current_hour:
                        # 조건 3: 타겟 프로세스가 실행 중인가?
                        if self.is_process_running(self.target_process):
                            # 알림 발송
                            self.send_alert(now)
                            self.last_alerted_hour = current_hour
                else:
                    # 분이 바뀌면 중복 방지 플래그 초기화
                    if current_minute != self.alert_minute and self.last_alerted_hour != -1:
                        # 다음 시간을 대비해 플래그를 초기화하되, 같은 시간대가 아닐 때만
                        if current_minute == (self.alert_minute + 1) % 60:
                            pass  # 이미 알림을 보낸 직후이므로 유지

                time.sleep(1)  # 1초 대기

            except Exception as e:
                self.add_log(f"❌ 오류 발생: {str(e)}")
                time.sleep(1)

    def is_process_running(self, process_name):
        """
        특정 프로세스가 실행 중인지 확인

        Args:
            process_name (str): 프로세스 이름 (예: "game.exe")

        Returns:
            bool: 프로세스 실행 여부
        """
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'].lower() == process_name.lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # 프로세스 접근 권한 없거나 종료된 경우 무시
                    pass
            return False
        except Exception as e:
            self.add_log(f"⚠️ 프로세스 확인 오류: {str(e)}")
            return False

    def send_alert(self, current_time):
        """
        알림 발송 (Toast + 사운드)

        Args:
            current_time (datetime): 현재 시각
        """
        time_str = current_time.strftime("%H:%M")
        message = f"🎮 {time_str} - {self.target_process} 실행 중!"

        # 로그 추가
        self.add_log(f"🔔 알림 발송: {message}")

        # Toast 알림
        if self.toaster:
            try:
                if hasattr(self.toaster, 'show_toast'):
                    # win10toast-click
                    threading.Thread(
                        target=lambda: self.toaster.show_toast(
                            "게임 시간 알림",
                            message,
                            duration=5,
                            threaded=True
                        ),
                        daemon=True
                    ).start()
            except Exception as e:
                self.add_log(f"⚠️ Toast 알림 오류: {str(e)}")
                try:
                    # plyer 대체
                    notification.notify(
                        title="게임 시간 알림",
                        message=message,
                        timeout=5
                    )
                except:
                    pass

        # 사운드 알림
        if self.sound_enabled and WINSOUND_AVAILABLE:
            try:
                threading.Thread(
                    target=lambda: winsound.MessageBeep(winsound.MB_ICONASTERISK),
                    daemon=True
                ).start()
            except Exception as e:
                self.add_log(f"⚠️ 사운드 재생 오류: {str(e)}")

    def add_log(self, message):
        """
        로그 영역에 메시지 추가

        Args:
            message (str): 로그 메시지
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        # UI 업데이트는 메인 스레드에서 실행
        self.root.after(0, lambda: self._append_log(log_message))

    def _append_log(self, message):
        """로그 텍스트 추가 (메인 스레드에서 실행)"""
        self.log_text.insert("end", message)
        self.log_text.see("end")  # 자동 스크롤

    def save_config(self):
        """설정을 JSON 파일로 저장"""
        config = {
            "target_process": self.target_process,
            "alert_minute": self.alert_minute,
            "sound_enabled": self.sound_enabled
        }

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.add_log("💾 설정이 저장되었습니다.")
        except Exception as e:
            self.add_log(f"❌ 설정 저장 오류: {str(e)}")

    def load_config(self):
        """설정을 JSON 파일에서 불러오기"""
        if not self.config_file.exists():
            self.add_log("ℹ️ 저장된 설정이 없습니다.")
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

            if self.sound_enabled:
                self.sound_switch.select()
            else:
                self.sound_switch.deselect()

            self.add_log("✅ 저장된 설정을 불러왔습니다.")

        except Exception as e:
            self.add_log(f"❌ 설정 불러오기 오류: {str(e)}")

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
