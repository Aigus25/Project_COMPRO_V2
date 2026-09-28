import struct
import os
import shutil
import random
import datetime

# รองรับ Main รุ่นใหม่ทั้ง V1 และ V2
# V1 ใช้ GROUP_STUDENTS
# V2 ใช้ DEFAULT_STUDENTS
try:
    from main_67_V2 import DEFAULT_STUDENTS
    GROUP_STUDENTS = [
        (student[1], student[2], student[3], student[4])
        for student in DEFAULT_STUDENTS
    ]
except (ImportError, ModuleNotFoundError):
    try:
        from main_67_V1 import GROUP_STUDENTS
    except (ImportError, ModuleNotFoundError):
        raise ImportError(
            "ไม่พบ main_67_V2.py หรือ main_67_V1.py "
            "กรุณาวางไฟล์ตัวรันไว้โฟลเดอร์เดียวกับ Main"
        )

# ============================================================
# สคริปต์สร้างข้อมูลทดสอบ: สมาชิกกลุ่ม 4 คน + การลงทะเบียนแบบสุ่ม
# หมายเหตุ:
# - ไม่สร้าง/ไม่แก้ไข courses.dat
# - ใช้รายวิชาและอาจารย์ที่มีอยู่ใน courses.dat
# - ใช้รายชื่อนักศึกษาจริงของสมาชิกกลุ่ม 4 คน
# - นักศึกษาแต่ละคนมี enrollment จำนวน 5 รายการ
# - รวมทั้งหมด 20 enrollment
# ============================================================

# ---- โครงสร้างต้องตรงกับ main.py ----
STUDENT_FORMAT = "<I 15s 50s 20s I I"
COURSE_FORMAT = "<I 15s 50s 20s I f I I 60s"
ENROLL_FORMAT = "<I 15s I 20s I"

STUDENT_SIZE = struct.calcsize(STUDENT_FORMAT)
COURSE_SIZE = struct.calcsize(COURSE_FORMAT)
ENROLL_SIZE = struct.calcsize(ENROLL_FORMAT)

STUDENT_FILE = "students.dat"
COURSE_FILE = "courses.dat"
ENROLL_FILE = "enrollments.dat"

# ให้สุ่มได้ผลเดิมทุกครั้ง
random.seed(2569)


def encode_fixed(s, size):
    """เข้ารหัสข้อความให้พอดีกับขนาด field และไม่ตัดกลาง UTF-8"""
    b = s.encode("utf-8")

    if len(b) > size:
        cut = size
        while cut > 0:
            try:
                b[:cut].decode("utf-8")
                break
            except UnicodeDecodeError:
                cut -= 1
        b = b[:cut]

    return b.ljust(size, b"\x00")


def decode_fixed(b):
    """ถอดข้อความจาก fixed-length field"""
    return b.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()


def backup(fname):
    """สำรองไฟล์เดิมก่อนสร้างข้อมูลใหม่"""
    if os.path.exists(fname):
        backup_name = fname.replace(
            ".dat", "_backup_before_4students.dat"
        )
        shutil.copy(fname, backup_name)
        print(f"  สำรอง {fname} -> {backup_name}")


# จำนวน enrollment ที่สุ่มให้สมาชิกแต่ละคน
ENROLLMENTS_PER_STUDENT = 5


# ============================================================
# อ่านนักศึกษาจาก students.dat
# ไม่สร้าง/แก้ไขข้อมูลนักศึกษาในไฟล์นี้
# ============================================================

def load_group_students():
    records = []
    group_codes = {student[0] for student in GROUP_STUDENTS}

    if not os.path.exists(STUDENT_FILE):
        raise FileNotFoundError(
            f"ไม่พบ {STUDENT_FILE} กรุณารัน Main อย่างน้อย 1 ครั้งก่อน"
        )

    with open(STUDENT_FILE, "rb") as f:
        while True:
            data = f.read(STUDENT_SIZE)
            if not data:
                break
            if len(data) != STUDENT_SIZE:
                break

            r = struct.unpack(STUDENT_FORMAT, data)
            code = decode_fixed(r[1])

            if r[5] == 1 and code in group_codes:
                records.append({
                    "code": code,
                    "name": decode_fixed(r[2]),
                    "major": decode_fixed(r[3]),
                    "year": r[4],
                })

    missing = group_codes - {student["code"] for student in records}
    if missing:
        raise ValueError(
            "ไม่พบสมาชิกกลุ่มใน students.dat: " + ", ".join(sorted(missing))
        )

    # เรียงตามลำดับ GROUP_STUDENTS เพื่อให้ผลแสดงเหมือนข้อมูลหลัก
    order = {student[0]: i for i, student in enumerate(GROUP_STUDENTS)}
    records.sort(key=lambda student: order[student["code"]])
    return records


# ============================================================
# อ่านรายวิชาจาก courses.dat
# ไม่สร้างรายวิชาใหม่
# ============================================================

def load_courses():
    if not os.path.exists(COURSE_FILE):
        raise FileNotFoundError(
            f"ไม่พบ {COURSE_FILE} กรุณาให้โปรแกรมหลักสร้างวิชาตั้งต้นก่อน"
        )

    courses = []

    with open(COURSE_FILE, "rb") as f:
        while True:
            data = f.read(COURSE_SIZE)

            if not data:
                break

            if len(data) != COURSE_SIZE:
                break

            r = struct.unpack(COURSE_FORMAT, data)

            course_id = r[0]
            code = decode_fixed(r[1])
            title = decode_fixed(r[2])
            credits = r[4]
            status = r[6]
            is_full = r[7]

            # ใช้เฉพาะวิชาที่ Active และยังไม่เต็ม
            if status == 1 and is_full == 0:
                courses.append({
                    "course_id": course_id,
                    "code": code,
                    "title": title,
                    "credits": credits
                })

    return courses


# ============================================================
# สุ่มการลงทะเบียน
# - นักศึกษาแต่ละคนลง 5 วิชา
# - ไม่ลงวิชาเดิมซ้ำ
# - รวมไม่เกิน 22 หน่วยกิต
# ============================================================

def gen_enrollments(student_codes, courses):
    records = []
    enroll_id = 1

    base_time = datetime.datetime(2026, 9, 1, 9, 0, 0)

    if len(courses) < ENROLLMENTS_PER_STUDENT:
        raise ValueError(
            f"มีรายวิชาที่ลงทะเบียนได้เพียง {len(courses)} วิชา "
            f"แต่ต้องใช้ {ENROLLMENTS_PER_STUDENT} วิชาต่อนักศึกษา"
        )

    for student_code in student_codes:
        # สุ่มชุดวิชาใหม่จนกว่าจะได้ 5 วิชาและหน่วยกิตรวมไม่เกิน 22
        selected = None

        for _ in range(1000):
            candidate = random.sample(courses, ENROLLMENTS_PER_STUDENT)
            total_credits = sum(course["credits"] for course in candidate)

            if total_credits <= 22:
                selected = candidate
                break

        if selected is None:
            raise ValueError(
                f"ไม่สามารถสุ่ม {ENROLLMENTS_PER_STUDENT} วิชาให้ {student_code} "
                "โดยให้หน่วยกิตรวมไม่เกิน 22 ได้"
            )

        # สร้างรายการลงทะเบียนจำนวน 5 รายการพอดี
        for course in selected:
            # ประมาณ 10% เป็น Cancelled
            status = 0 if random.random() < 0.10 else 1

            date_str = (
                base_time +
                datetime.timedelta(minutes=enroll_id * 7)
            ).strftime("%Y-%m-%d %H:%M:%S")

            records.append(
                struct.pack(
                    ENROLL_FORMAT,
                    enroll_id,
                    encode_fixed(student_code, 15),
                    course["course_id"],
                    encode_fixed(date_str, 20),
                    status
                )
            )

            enroll_id += 1

    return records


# ============================================================
# Main
# ============================================================

def main():
    print("=== สร้างข้อมูลสมาชิกกลุ่ม 4 คน + การลงทะเบียนแบบสุ่ม ===\n")

    print("ตรวจสอบไฟล์รายวิชา:")
    if not os.path.exists(COURSE_FILE):
        print(f"  ERROR: ไม่พบ {COURSE_FILE}")
        print("  กรุณารันโปรแกรมหลักอย่างน้อย 1 ครั้ง")
        print("  เพื่อให้ระบบสร้าง DEFAULT_COURSES ก่อน")
        return

    courses = load_courses()

    if not courses:
        print("  ERROR: ไม่มีรายวิชา Active ที่ยังเปิดรับลงทะเบียน")
        return

    print(f"  พบรายวิชาที่ใช้ลงทะเบียนได้ {len(courses)} วิชา")

    print("\nตรวจสอบข้อมูลนักศึกษาสมาชิกกลุ่ม:")
    students = load_group_students()
    student_codes = [student["code"] for student in students]
    print(f"  พบสมาชิกกลุ่ม {len(students)} คนใน {STUDENT_FILE}")

    print("\nสำรองไฟล์ enrollment เดิม:")
    backup(ENROLL_FILE)

    print("กำลังสุ่มการลงทะเบียน...")
    enroll_records = gen_enrollments(student_codes, courses)


    # เขียน enrollments.dat
    with open(ENROLL_FILE, "wb") as f:
        for record in enroll_records:
            f.write(record)

    print("\nสร้างข้อมูลเสร็จเรียบร้อย")
    print("-" * 55)
    print(
        f"  {STUDENT_FILE:<18}: ไม่แก้ไข ({len(students):>3} สมาชิกกลุ่ม)"
    )
    print(
        f"  {ENROLL_FILE:<18}: {len(enroll_records):>3} records "
        f"({os.path.getsize(ENROLL_FILE):>6} bytes)"
    )
    print(f"  courses.dat        : ไม่แก้ไข ({len(courses)} วิชา)")
    print("-" * 55)

    print("\nรายชื่อนักศึกษา:")
    for i, student in enumerate(students, 1):
        print(
            f"  {i:02d}. {student['code']} | "
            f"{student['name']} | {student['major']} | "
            f"ปี {student['year']} | {ENROLLMENTS_PER_STUDENT} enrollments"
        )

    print("\nเสร็จแล้ว สามารถรัน main.py ได้เลย")


if __name__ == "__main__":
    main()
