"""
สคริปต์แปลง courses.dat จากรูปแบบเก่า (ไม่มีฟิลด์ผู้สอน) เป็นรูปแบบใหม่
(เพิ่มฟิลด์ instructor 50 ไบต์ต่อท้าย) โดยไม่ทำข้อมูลเดิมหาย

วิธีใช้:
1. วางไฟล์นี้ไว้โฟลเดอร์เดียวกับ courses.dat เวอร์ชันเก่า (105 ไบต์/record)
2. รัน: python migrate_courses.py
3. จะได้ courses.dat ใหม่ (155 ไบต์/record, instructor เป็นค่าว่างทุก record)
   ไฟล์เก่าจะถูกสำรองไว้ที่ courses_backup_old.dat
"""
import struct
import shutil
import os

OLD_FORMAT = "<I 15s 50s 20s I f I I"           # รูปแบบเดิม (105 ไบต์)
NEW_FORMAT = "<I 15s 50s 20s I f I I 60s"       # รูปแบบใหม่ (165 ไบต์ มี instructor)

OLD_SIZE = struct.calcsize(OLD_FORMAT)
NEW_SIZE = struct.calcsize(NEW_FORMAT)

COURSE_FILE = "courses.dat"
BACKUP_FILE = "courses_backup_old.dat"


def main():
    if not os.path.exists(COURSE_FILE):
        print(f"ไม่พบไฟล์ {COURSE_FILE}")
        return

    size_on_disk = os.path.getsize(COURSE_FILE)
    if size_on_disk % NEW_SIZE == 0 and size_on_disk % OLD_SIZE != 0:
        print("ไฟล์นี้เป็นรูปแบบใหม่ (มีฟิลด์ instructor) อยู่แล้ว ไม่ต้อง migrate")
        return
    if size_on_disk % OLD_SIZE != 0:
        print("ขนาดไฟล์ไม่ตรงกับรูปแบบเก่าหรือใหม่เลย ตรวจสอบไฟล์อีกครั้งก่อน migrate")
        return

    shutil.copy(COURSE_FILE, BACKUP_FILE)
    print(f"สำรองไฟล์เดิมไว้ที่ {BACKUP_FILE} แล้ว")

    old_records = []
    with open(COURSE_FILE, "rb") as f:
        while True:
            data = f.read(OLD_SIZE)
            if not data:
                break
            old_records.append(struct.unpack(OLD_FORMAT, data))

    empty_instructor = b"".ljust(60, b"\x00")
    with open(COURSE_FILE, "wb") as f:
        for r in old_records:
            new_record = struct.pack(NEW_FORMAT, *r, empty_instructor)
            f.write(new_record)

    print(f"แปลงข้อมูลสำเร็จ! {len(old_records)} record(s) -> รูปแบบใหม่ ({NEW_SIZE} ไบต์/record)")
    print("ฟิลด์ instructor ของทุกวิชาตั้งเป็นค่าว่าง ใช้เมนู 'อาจารย์ผู้สอน' ในโปรแกรมเพื่อกำหนดภายหลังได้")


if __name__ == "__main__":
    main()
