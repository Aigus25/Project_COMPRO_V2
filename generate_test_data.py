"""
===============================================================================
  สคริปต์สร้างชุดข้อมูลทดสอบ (Test Data Generator)
  วัตถุประสงค์: สร้างข้อมูลทดสอบ >= 50 ระเบียนหลักต่อไฟล์ ตามที่โจทย์กำหนด
                พร้อมกรณีขอบ (edge cases) และกรณีข้อมูลซ้ำ
===============================================================================

วิธีใช้:
    python generate_test_data.py

จะสร้างไฟล์ students.dat, courses.dat, enrollments.dat ใหม่ทับของเดิม
(ถ้ามีไฟล์เดิมอยู่ จะสำรองไว้เป็น *_backup_before_testdata.dat ก่อน)

ชุดข้อมูลที่สร้างประกอบด้วย:
  - นักศึกษา 60 คน (มี soft-deleted 5 คน, มี ID/ปีซ้ำกันหลายคนตามดีไซน์ระบบ)
  - รายวิชา 55 วิชา (มี soft-deleted 5 วิชา, มีทั้งที่มี/ไม่มีอาจารย์ผู้สอน)
  - การลงทะเบียน 80 รายการ (มี cancelled 8 รายการ)
  - กรณีขอบ: ชื่อภาษาไทยยาวเกินขนาดฟิลด์, ค่าธรรมเนียม 0 บาท, วิชาเต็ม
"""

import struct
import os
import shutil
import random
import datetime

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

random.seed(2569)  # ตั้ง seed ให้ผลลัพธ์ซ้ำเดิมได้ทุกครั้ง (reproducible)


def encode_fixed(s, size):
    """เข้ารหัสสตริงให้พอดีขนาด โดยไม่ตัดกลางตัวอักษรหลายไบต์ (กันภาษาไทยเพี้ยน)"""
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


def backup(fname):
    if os.path.exists(fname):
        backup_name = fname.replace(".dat", "_backup_before_testdata.dat")
        shutil.copy(fname, backup_name)
        print(f"  สำรอง {fname} -> {backup_name}")


# ============================================================
#  ข้อมูลตั้งต้นสำหรับสุ่ม
# ============================================================

FIRST_NAMES = ["สมชาย", "สมหญิง", "อนันต์", "ปิยะ", "ธนกร", "ศิริพร", "วรรณา", "กิตติ",
               "นภัส", "ชลธิชา", "ภาคิน", "ธีรเดช", "พิมพ์ชนก", "อรทัย", "ณัฐวุฒิ",
               "สุชาดา", "ปกรณ์", "ชนิดา", "วีรภัทร", "อารยา"]
LAST_NAMES = ["ใจดี", "รักเรียน", "ทองแท้", "ศรีสุข", "มั่นคง", "พูนทรัพย์", "วงศ์ไทย",
              "แสงทอง", "บุญมี", "เจริญสุข", "นะจ๊ะ", "อยู่ดี", "สินทรัพย์", "พัฒนา"]
MAJORS = ["INE", "IT", "CA", "CS", "SE", "DS", "EE", "ME"]

COURSE_DATA = [
    ("COM", "Computer Programming", "Core"), ("COM", "Data Structures", "Core"),
    ("COM", "Algorithm Design", "Core"), ("COM", "Database Systems", "Core"),
    ("COM", "Operating Systems", "Core"), ("COM", "Computer Networks", "Core"),
    ("COM", "Software Engineering", "Core"), ("COM", "Web Development", "Elective"),
    ("COM", "Mobile App Development", "Elective"), ("COM", "Machine Learning", "Elective"),
    ("COM", "Data Engineering", "Elective"), ("COM", "Cloud Computing", "Elective"),
    ("COM", "Cyber Security", "Elective"), ("COM", "Computer Graphics", "Elective"),
    ("COM", "Artificial Intelligence", "Elective"),
    ("GEN", "English Communication", "GenEd"), ("GEN", "Thai for Communication", "GenEd"),
    ("GEN", "Life and Social Skills", "GenEd"), ("GEN", "Critical Thinking", "GenEd"),
    ("GEN", "Environmental Science", "GenEd"), ("GEN", "Business English", "GenEd"),
    ("MTH", "Calculus I", "Core"), ("MTH", "Calculus II", "Core"),
    ("MTH", "Linear Algebra", "Core"), ("MTH", "Discrete Mathematics", "Core"),
    ("MTH", "Statistics for Engineers", "Core"),
    ("PHY", "Physics I", "Core"), ("PHY", "Physics Laboratory", "Core"),
    ("CHM", "General Chemistry", "Core"), ("CHM", "Chemistry Laboratory", "Core"),
    ("SPT", "Table Tennis", "Sport"), ("SPT", "Basketball", "Sport"),
    ("SPT", "Swimming", "Sport"), ("SPT", "Badminton", "Sport"),
    ("SPT", "Football", "Sport"), ("SPT", "Volleyball", "Sport"),
    ("ART", "Music Appreciation", "Elective"), ("ART", "Digital Photography", "Elective"),
    ("ART", "Design Thinking", "Elective"), ("ART", "Creative Writing", "Elective"),
    ("BUS", "Principles of Management", "Elective"), ("BUS", "Marketing Basics", "Elective"),
    ("BUS", "Accounting for Non-Majors", "Elective"), ("BUS", "Entrepreneurship", "Elective"),
    ("BUS", "Project Management", "Elective"),
    ("ENG", "Engineering Drawing", "Core"), ("ENG", "Materials Science", "Core"),
    ("ENG", "Thermodynamics", "Core"), ("ENG", "Circuit Analysis", "Core"),
    ("ENG", "Digital Logic Design", "Core"),
    ("LAW", "Introduction to Law", "GenEd"), ("LAW", "Cyber Law and Ethics", "GenEd"),
    ("PSY", "General Psychology", "GenEd"), ("PSY", "Human Behavior", "GenEd"),
    ("HIS", "Thai History and Culture", "GenEd"),
]

INSTRUCTORS = ["อ.สมศักดิ์ วิชาการ", "อ.ดร.ปราณี ใฝ่รู้", "ผศ.ดร.ธนา ก้าวหน้า",
               "อ.มาลี สอนดี", "รศ.ดร.วิชัย ปัญญาเลิศ", "อ.สุดา เมตตา", ""]


def gen_students():
    """สร้างนักศึกษา 60 คน (55 active + 5 soft-deleted)"""
    records = []
    used_codes = set()
    for i in range(60):
        # Student ID = ปีการศึกษาที่เข้า (ซ้ำกันได้ตามดีไซน์ระบบ)
        year_id = random.choice([67, 68, 69])
        # รหัสนักศึกษา 13 หลัก ห้ามซ้ำ
        while True:
            code = str(random.randint(1000000000000, 9999999999999))
            if code not in used_codes:
                used_codes.add(code)
                break

        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        # กรณีขอบ: ชื่อยาวเกินขนาดฟิลด์ 50 ไบต์ (ทดสอบการตัดข้อความภาษาไทย)
        if i == 7:
            name = "ณัฐวรรณวิไลลักษณ์ ประเสริฐศรีสกุลวงศ์ไพบูลย์ทรัพย์"
        major = random.choice(MAJORS)
        # กรณีขอบ: สาขาที่ยาวเต็มขนาดฟิลด์พอดี
        if i == 12:
            major = "Computer Engineer"
        study_year = random.randint(1, 4)
        status = 0 if i in (5, 17, 29, 41, 53) else 1  # soft-deleted 5 คน

        records.append(struct.pack(
            STUDENT_FORMAT, year_id, encode_fixed(code, 15), encode_fixed(name, 50),
            encode_fixed(major, 20), study_year, status
        ))
    return records, used_codes


def gen_courses():
    """สร้างรายวิชา 55 วิชา (50 active + 5 soft-deleted)"""
    records = []
    course_info = []  # เก็บ (course_id, credits, is_active, is_full) ไว้ใช้ตอนสร้าง enrollment
    for i, (prefix, title, category) in enumerate(COURSE_DATA):
        course_id = 1001 + i
        code = f"{prefix}{101 + i}"
        credits = random.choice([1, 2, 3, 3, 3, 4])
        # กรณีขอบ: วิชาที่ค่าธรรมเนียม 0 บาท และวิชาที่ค่าธรรมเนียมสูง
        if category == "Sport":
            fee = 0.0
        elif i == 9:
            fee = 4500.0
        else:
            fee = float(random.choice([500, 800, 1000, 1200, 1500, 2000]))
        status = 0 if i in (6, 19, 28, 37, 48) else 1  # soft-deleted 5 วิชา
        is_full = 1 if i in (3, 15, 31) else 0  # วิชาที่เต็มแล้ว 3 วิชา
        instructor = random.choice(INSTRUCTORS)

        records.append(struct.pack(
            COURSE_FORMAT, course_id, encode_fixed(code, 15), encode_fixed(title, 50),
            encode_fixed(category, 20), credits, fee, status, is_full,
            encode_fixed(instructor, 60)
        ))
        course_info.append((course_id, credits, status == 1, is_full == 1))
    return records, course_info


def gen_enrollments(student_codes, course_info):
    """สร้างการลงทะเบียน 80 รายการ (72 active + 8 cancelled) โดยเคารพเพดาน 22 หน่วยกิต"""
    records = []
    # เลือกเฉพาะวิชาที่ Active และยังไม่เต็ม
    open_courses = [(cid, cr) for cid, cr, active, full in course_info if active and not full]
    codes = list(student_codes)

    credits_used = {}   # {student_code: หน่วยกิตรวม}
    taken = set()       # กันลงทะเบียนซ้ำ (student_code, course_id)
    base_time = datetime.datetime(2026, 9, 1, 9, 0, 0)

    enroll_id = 1
    attempts = 0
    while len(records) < 80 and attempts < 2000:
        attempts += 1
        code = random.choice(codes)
        cid, credits = random.choice(open_courses)

        if (code, cid) in taken:
            continue
        if credits_used.get(code, 0) + credits > 22:  # เคารพเพดานหน่วยกิต
            continue

        taken.add((code, cid))
        credits_used[code] = credits_used.get(code, 0) + credits
        status = 0 if enroll_id % 10 == 0 else 1  # cancelled ทุกๆ รายการที่ 10
        date_str = (base_time + datetime.timedelta(minutes=enroll_id * 7)).strftime("%Y-%m-%d %H:%M:%S")

        records.append(struct.pack(
            ENROLL_FORMAT, enroll_id, encode_fixed(code, 15), cid,
            encode_fixed(date_str, 20), status
        ))
        enroll_id += 1
    return records


def main():
    print("=== สร้างชุดข้อมูลทดสอบ (Test Data Generator) ===\n")
    print("สำรองไฟล์เดิม (ถ้ามี):")
    for fname in (STUDENT_FILE, COURSE_FILE, ENROLL_FILE):
        backup(fname)

    print("\nกำลังสร้างข้อมูล...")
    student_records, student_codes = gen_students()
    course_records, course_info = gen_courses()
    enroll_records = gen_enrollments(student_codes, course_info)

    with open(STUDENT_FILE, "wb") as f:
        for r in student_records:
            f.write(r)
    with open(COURSE_FILE, "wb") as f:
        for r in course_records:
            f.write(r)
    with open(ENROLL_FILE, "wb") as f:
        for r in enroll_records:
            f.write(r)

    print(f"\nสร้างข้อมูลเสร็จเรียบร้อย:")
    print(f"  {STUDENT_FILE:<18} : {len(student_records):>3} records "
          f"({os.path.getsize(STUDENT_FILE):>6} ไบต์ @ {STUDENT_SIZE} ไบต์/record)")
    print(f"  {COURSE_FILE:<18} : {len(course_records):>3} records "
          f"({os.path.getsize(COURSE_FILE):>6} ไบต์ @ {COURSE_SIZE} ไบต์/record)")
    print(f"  {ENROLL_FILE:<18} : {len(enroll_records):>3} records "
          f"({os.path.getsize(ENROLL_FILE):>6} ไบต์ @ {ENROLL_SIZE} ไบต์/record)")
    print(f"\n  รวมทั้งหมด : {len(student_records) + len(course_records) + len(enroll_records)} records")
    print("\nกรณีขอบที่รวมอยู่ในชุดข้อมูล:")
    print("  - นักศึกษาที่ถูก Soft Delete 5 คน / รายวิชาที่ถูก Soft Delete 5 วิชา")
    print("  - การลงทะเบียนที่ถูกยกเลิก (Cancelled) หลายรายการ")
    print("  - ชื่อภาษาไทยยาวเกินขนาดฟิลด์ (ทดสอบการตัดข้อความแบบปลอดภัย)")
    print("  - Student ID (ปีการศึกษา) ซ้ำกันหลายคน ตามดีไซน์ของระบบ")
    print("  - รายวิชาค่าธรรมเนียม 0 บาท และวิชาที่เต็มแล้ว (ปิดรับ)")
    print("  - รายวิชาที่ยังไม่มีอาจารย์ผู้สอน")
    print("\nรันโปรแกรมหลักด้วย: python main.py")


if __name__ == "__main__":
    main()
