"""라이브러리 테스트"""
import sys

print("Python version:", sys.version)
print("=" * 50)

try:
    import customtkinter as ctk
    print("✓ customtkinter OK")
except Exception as e:
    print(f"✗ customtkinter ERROR: {e}")
    sys.exit(1)

try:
    import psutil
    print("✓ psutil OK")
except Exception as e:
    print(f"✗ psutil ERROR: {e}")
    sys.exit(1)

try:
    from winotify import Notification
    print("✓ winotify OK")
except Exception as e:
    print(f"✗ winotify ERROR: {e}")
    sys.exit(1)

print("=" * 50)
print("모든 라이브러리 OK! 간단한 창 테스트 시작...")

try:
    root = ctk.CTk()
    root.title("Test")
    root.geometry("300x200")

    label = ctk.CTkLabel(root, text="테스트 성공!", font=("Arial", 20))
    label.pack(pady=50)

    button = ctk.CTkButton(root, text="닫기", command=root.destroy)
    button.pack(pady=20)

    print("✓ 창이 생성되었습니다. 창을 닫으면 프로그램이 종료됩니다.")
    root.mainloop()

except Exception as e:
    print(f"✗ 창 생성 ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("테스트 완료!")
