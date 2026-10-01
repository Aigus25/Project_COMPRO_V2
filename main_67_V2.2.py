import struct
import unicodedata
import os
import datetime

# ============================================================
#  โครงสร้างไฟล์ไบนารีทั้ง 3 ไฟล์ (Fixed-length record, Little-Endian)
# ============================================================

# 1) นักศึกษา (Student)
STUDENT_FORMAT = "<I 15s 50s 20s I I"
# id(I) | student_code(15s) | name(50s) | major(20s) | year(I) | status(I: 1=active,0=deleted)
STUDENT_SIZE = struct.calcsize(STUDENT_FORMAT)
STUDENT_FILE = "students.dat"

# 2) รายวิชา (Course)
COURSE_FORMAT = "<I 15s 50s 20s I f I I 60s"
# id(I) | code(15s) | title(50s) | category(20s) | credits(I) | fee(f) | status(I) | full(I) | instructor(60s)
COURSE_SIZE = struct.calcsize(COURSE_FORMAT)
COURSE_FILE = "courses.dat"

# 3) การลงทะเบียน (Enrollment)
# เปลี่ยนการเก็บจาก student_id -> student_code (15s) เพื่อรองรับ ID ซ้ำ
ENROLL_FORMAT = "<I 15s I 20s I"
# enroll_id(I) | student_code(15s) | course_id(I) | enroll_date(20s) | status(I: 1=ลงทะเบียนอยู่,0=ยกเลิก)
ENROLL_SIZE = struct.calcsize(ENROLL_FORMAT)
ENROLL_FILE = "enrollments.dat"

LOG_FILE = "operations.log"

# กฎระเบียบการลงทะเบียน: นักศึกษา 1 คนลงทะเบียนรวมกันได้ไม่เกินกี่หน่วยกิตต่อภาคเรียน
MAX_CREDITS_PER_STUDENT = 16


# ============================================================
#  ฟังก์ชันช่วยทั่วไป
# ============================================================

def log_action(text):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {text}\n")


def read_all_records(filename, fmt, size):
    records = []
    if not os.path.exists(filename):
        return records
    with open(filename, "rb") as f:
        while True:
            data = f.read(size)
            if not data:
                break
            if len(data) != size:
                print(f"คำเตือน: พบข้อมูลไม่ครบ record ในไฟล์ {filename} (ข้ามส่วนนี้)")
                break
            records.append(struct.unpack(fmt, data))
    return records


def decode_str(b):
    return b.rstrip(b"\x00").decode("utf-8", errors="replace")


def encode_fixed(s, size):
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


def ask_int(prompt, allow_empty=False, default=None):
    while True:
        s = input(prompt).strip()
        if allow_empty and s == "":
            return default
        try:
            return int(s)
        except ValueError:
            print("กรุณาป้อนตัวเลขจำนวนเต็มเท่านั้น ลองใหม่อีกครั้ง")


def ask_float(prompt, allow_empty=False, default=None):
    while True:
        s = input(prompt).strip()
        if allow_empty and s == "":
            return default
        try:
            return float(s)
        except ValueError:
            print("กรุณาป้อนตัวเลขเท่านั้น ลองใหม่อีกครั้ง")


def ask_text(prompt, allow_empty=False, default=None):
    """รับข้อความที่เป็นตัวอักษรและช่องว่าง (อนุญาต . และ - สำหรับคำนำหน้าชื่อ/ชื่อสกุล)"""
    while True:
        s = input(prompt).strip()
        if allow_empty and s == "":
            return default
        if s and all(ch.isalpha() or unicodedata.category(ch).startswith("M") or ch.isspace() or ch in ".-" for ch in s):
            return s
        print("กรุณาป้อนตัวอักษรเท่านั้น (สามารถเว้นวรรคหรือใช้ . และ - ได้)")


def ask_bounded_int(prompt, minimum, maximum, allow_empty=False, default=None):
    while True:
        s = input(prompt).strip()
        if allow_empty and s == "":
            return default
        try:
            value = int(s)
            if minimum <= value <= maximum:
                return value
            print(f"กรุณาป้อนค่าระหว่าง {minimum}-{maximum} เท่านั้น")
        except ValueError:
            print("กรุณาป้อนตัวเลขจำนวนเต็มเท่านั้น ลองใหม่อีกครั้ง")


def ask_numeric_code(prompt, label="รหัสวิชา"):
    while True:
        s = input(prompt).strip()
        if s.isdigit():
            return s
        print(f"{label}ต้องเป็นตัวเลขเท่านั้น ลองใหม่อีกครั้ง")


def ask_student_code(prompt, check_duplicate=True):
    while True:
        s = input(prompt).strip()
        if not (len(s) == 13 and s.isdigit()):
            print("รหัสนักศึกษาต้องเป็นตัวเลขล้วน 13 หลักเท่านั้น ลองใหม่อีกครั้ง")
            continue
        if check_duplicate:
            duplicate = any(
                r[5] == 1 and decode_str(r[1]) == s
                for r in read_all_records(STUDENT_FILE, STUDENT_FORMAT, STUDENT_SIZE)
            )
            if duplicate:
                print(f"รหัสนักศึกษา '{s}' มีอยู่แล้วในระบบ ห้ามซ้ำ ลองใหม่อีกครั้ง")
                continue
        return s


def find_student_by_code(code_str):
    """ค้นหานักศึกษาจาก student_code (13 หลัก)"""
    for r in read_all_records(STUDENT_FILE, STUDENT_FORMAT, STUDENT_SIZE):
        if r[5] == 1 and decode_str(r[1]) == code_str:
            return r
    return None


def write_record(filename, fmt, size, packed_data, status_index):
    """
    เขียน record ใหม่ลงไฟล์ไบนารี โดยใช้หลักการ Slot Reuse (Free-list)
    1. วนหา record แรกที่ถูก Soft Delete แล้ว (status == 0)
    2. ถ้าเจอ -> seek() ไปเขียนทับช่องว่างนั้น (ไฟล์ไม่โตขึ้น)
    3. ถ้าไม่เจอช่องว่างเลย -> เขียนต่อท้ายไฟล์ด้วยโหมด 'ab'
    คืนค่า True ถ้าใช้ช่องว่างเดิมซ้ำ, False ถ้าต่อท้ายไฟล์ใหม่
    """
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        with open(filename, "r+b") as f:
            index = 0
            while True:
                offset = index * size
                f.seek(offset)
                data = f.read(size)
                if not data or len(data) != size:
                    break
                unpacked = struct.unpack(fmt, data)
                if unpacked[status_index] == 0:  # เจอช่องว่างจากการลบ
                    f.seek(offset)
                    f.write(packed_data)
                    return True
                index += 1

    with open(filename, "ab") as f:
        f.write(packed_data)
    return False


def id_exists(filename, fmt, size, target_id, active_only=True):
    for rec in read_all_records(filename, fmt, size):
        if rec[0] == target_id:
            if not active_only:
                return True
            status = rec[-1] if filename != COURSE_FILE else rec[6]
            if status == 1:
                return True
    return False


# ============================================================
#  ข้อมูลสมาชิกกลุ่ม (Default Students)
# ============================================================
# เก็บข้อมูลสมาชิกกลุ่มที่ต้องมีในระบบตั้งต้น
# และใช้โครงสร้าง Student record เดิมทุกประการ
DEFAULT_STUDENTS = [
    (69, "6906022610410", "Kuananon Puriphongphan", "INE", 1),
    (69, "6906022610029", "Thitiwat Thaicharoen", "INE", 1),
    (68, "6806022610241", "Laksika Phomphan", "INE", 2),
    (68, "6806022610259", "Pannawit Numwong", "INE", 2),
]


def seed_default_students():
    """เพิ่มข้อมูลสมาชิกกลุ่มที่ยังไม่มีใน students.dat โดยไม่สร้างข้อมูลซ้ำ"""
    existing_students = read_all_records(STUDENT_FILE, STUDENT_FORMAT, STUDENT_SIZE)
    existing_codes = {
        decode_str(r[1]).strip()
        for r in existing_students
        if r[5] == 1
    }

    students_to_add = [
        student for student in DEFAULT_STUDENTS
        if student[1] not in existing_codes
    ]

    if not students_to_add:
        return

    for student_id, student_code, name, major, year in students_to_add:
        packed = struct.pack(
            STUDENT_FORMAT,
            student_id,
            encode_fixed(student_code, 15),
            encode_fixed(name, 50),
            encode_fixed(major, 20),
            year,
            1,
        )
        reused = write_record(
            STUDENT_FILE,
            STUDENT_FORMAT,
            STUDENT_SIZE,
            packed,
            5,
        )
        log_action(
            f"เพิ่มข้อมูลสมาชิกกลุ่ม StudentCode={student_code} "
            f"ชื่อ={name} ID/ปี={student_id}"
            + (" [ใช้ช่องว่างเดิมซ้ำ]" if reused else "")
        )


# ============================================================
#  1) นักศึกษา (Student)
# ============================================================

def add_student():
    print("\n--- เพิ่มนักศึกษาใหม่ ---")
    student_id = ask_bounded_int("ป้อน Student ID / ปีการศึกษา (เช่น 68, 69): ", 1, 69)
    code = ask_student_code("ป้อนรหัสนักศึกษา (ตัวเลข 13 หลัก เช่น 6906022610067): ")
    name = ask_text("ป้อนชื่อ-สกุล: ")
    major = ask_text("ป้อนสาขาวิชา: ")
    year = ask_bounded_int("ป้อนชั้นปี: ", 1, 5)

    code_b = encode_fixed(code, 15)
    name_b = encode_fixed(name, 50)
    major_b = encode_fixed(major, 20)

    packed = struct.pack(STUDENT_FORMAT, student_id, code_b, name_b, major_b, year, 1)
    reused = write_record(STUDENT_FILE, STUDENT_FORMAT, STUDENT_SIZE, packed, 5)
    log_action(f"เพิ่มนักศึกษา รหัส={code} ID/ปี={student_id} ชื่อ={name}"
               + (" [ใช้ช่องว่างเดิมซ้ำ]" if reused else ""))
    print(f"บันทึกนักศึกษา '{name}' เรียบร้อย!"
          + (" (นำช่องว่างจากข้อมูลที่ถูกลบกลับมาใช้ใหม่)" if reused else "") + "\n")


def update_student():
    print("\n--- แก้ไขข้อมูลนักศึกษา ---")
    if not os.path.exists(STUDENT_FILE) or os.path.getsize(STUDENT_FILE) == 0:
        print("ยังไม่มีข้อมูลในระบบ\n")
        return
    
    search_code = ask_student_code("ป้อนรหัสนักศึกษา 13 หลัก ที่ต้องการแก้ไข: ", check_duplicate=False)

    with open(STUDENT_FILE, "r+b") as f:
        index = 0
        found = False
        while True:
            offset = index * STUDENT_SIZE
            f.seek(offset)
            data = f.read(STUDENT_SIZE)
            if not data:
                break
            u = struct.unpack(STUDENT_FORMAT, data)
            if decode_str(u[1]) == search_code and u[5] == 1:
                found = True
                curr_name = decode_str(u[2])
                print(f"พบข้อมูลเดิม: {curr_name} (ID/ปี: {u[0]})")
                new_name = ask_text("ชื่อใหม่ (Enter = ไม่เปลี่ยน): ", allow_empty=True, default=curr_name)
                new_year = ask_bounded_int("ชั้นปีใหม่ (Enter = ไม่เปลี่ยน): ", 1, 5, allow_empty=True, default=u[4])

                name_b = encode_fixed(new_name, 50)
                packed_new = struct.pack(STUDENT_FORMAT, u[0], u[1], name_b, u[3], new_year, 1)
                f.seek(offset)
                f.write(packed_new)
                log_action(f"แก้ไขนักศึกษา รหัส={search_code}")
                print("แก้ไขข้อมูลเรียบร้อยแล้ว!\n")
                break
            index += 1
        if not found:
            print("ไม่พบนักศึกษารหัสนี้ หรือถูกลบไปแล้ว\n")


def delete_student():
    print("\n--- ลบนักศึกษา (Soft Delete) ---")
    if not os.path.exists(STUDENT_FILE) or os.path.getsize(STUDENT_FILE) == 0:
        print("ยังไม่มีข้อมูลในระบบ\n")
        return
    
    search_code = ask_student_code("ป้อนรหัสนักศึกษา 13 หลัก ที่ต้องการลบ: ", check_duplicate=False)

    with open(STUDENT_FILE, "r+b") as f:
        index = 0
        found = False
        while True:
            offset = index * STUDENT_SIZE
            f.seek(offset)
            data = f.read(STUDENT_SIZE)
            if not data:
                break
            u = struct.unpack(STUDENT_FORMAT, data)
            if decode_str(u[1]) == search_code and u[5] == 1:
                found = True
                packed_del = struct.pack(STUDENT_FORMAT, u[0], u[1], u[2], u[3], u[4], 0)
                f.seek(offset)
                f.write(packed_del)
                log_action(f"ลบนักศึกษา รหัส={search_code}")
                print(f"ลบนักศึกษารหัส {search_code} เรียบร้อยแล้ว!\n")
                break
            index += 1
        if not found:
            print("ไม่พบนักศึกษานี้\n")


def view_students():
    print("\n--- เมนูย่อย: ดูข้อมูลนักศึกษา ---")
    print("1) ดูทั้งหมด")
    print("2) ค้นหาตามรหัสนักศึกษา (13 หลัก)")
    print("3) ค้นหาตาม Student ID / ปีการศึกษา (แสดงทุกคนในกลุ่ม)")
    print("4) ดูแบบกรอง (ตามสาขา)")
    print("5) สถิติโดยสรุป")
    choice = input("เลือก: ").strip()
    records = read_all_records(STUDENT_FILE, STUDENT_FORMAT, STUDENT_SIZE)
    active = [r for r in records if r[5] == 1]

    if choice == "1":
        if not active:
            print("ไม่มีข้อมูลนักศึกษา (Active)\n")
            return
        for i, r in enumerate(active, 1):
            print(f"[{i}] ID/ปี:{r[0]} รหัส:{decode_str(r[1])} ชื่อ:{decode_str(r[2])} "
                  f"สาขา:{decode_str(r[3])} ชั้นปี:{r[4]}")
    elif choice == "2":
        code = ask_student_code("ป้อนรหัสนักศึกษา 13 หลัก: ", check_duplicate=False)
        found = [r for r in active if decode_str(r[1]) == code]
        if not found:
            print("ไม่พบนักศึกษานี้\n")
        else:
            r = found[0]
            print(f"ID/ปี:{r[0]} รหัส:{decode_str(r[1])} ชื่อ:{decode_str(r[2])} "
                  f"สาขา:{decode_str(r[3])} ชั้นปี:{r[4]}")
    elif choice == "3":
        sid = ask_int("ป้อน Student ID / ปีการศึกษา: ")
        found = [r for r in active if r[0] == sid]
        if not found:
            print(f"ไม่พบนักศึกษาในกลุ่ม ID/ปี {sid}\n")
        else:
            print(f"\nพบนักศึกษาในกลุ่ม ID/ปี {sid} ทั้งหมด {len(found)} คน:")
            for i, r in enumerate(found, 1):
                print(f"[{i}] รหัส:{decode_str(r[1])} ชื่อ:{decode_str(r[2])} สาขา:{decode_str(r[3])}")
    elif choice == "4":
        major_kw = input("ป้อนคำค้นสาขาวิชา: ").strip().lower()
        found = [r for r in active if major_kw in decode_str(r[3]).lower()]
        if not found:
            print("ไม่พบนักศึกษาที่ตรงเงื่อนไข\n")
        for r in found:
            print(f"ID/ปี:{r[0]} รหัส:{decode_str(r[1])} ชื่อ:{decode_str(r[2])} สาขา:{decode_str(r[3])}")
    elif choice == "5":
        print(f"จำนวนนักศึกษาทั้งหมด (records) : {len(records)}")
        print(f"จำนวนนักศึกษา Active            : {len(active)}")
        print(f"จำนวนนักศึกษาที่ถูกลบ            : {len(records) - len(active)}")
    else:
        print("เลือกเมนูไม่ถูกต้อง\n")
    print()


# ============================================================
#  2) รายวิชา (Course)
# ============================================================

def add_course():
    print("\n--- เพิ่มรายวิชาใหม่ ---")
    course_id = ask_int("ป้อน Course ID (เช่น 1001): ")
    code = ask_numeric_code("ป้อนรหัสวิชา (ตัวเลขเท่านั้น เช่น 060233115): ")
    title = input("ป้อนชื่อรายวิชา: ").strip()

    while True:
        category = input("ป้อนหมวดวิชา (Core / Elective / GenEd): ").strip()
        if category.lower() in {"core", "elective", "gened"}:
            category = {"core": "Core", "elective": "Elective", "gened": "GenEd"}[category.lower()]
            break
        print("หมวดวิชาต้องเป็น Core, Elective หรือ GenEd เท่านั้น")

    credits = ask_bounded_int("ป้อนจำนวนหน่วยกิต (1-3): ", 1, 3)
    fee = ask_float("ป้อนค่าธรรมเนียมวิชา (บาท): ")
    instructor = ask_text("ป้อนชื่ออาจารย์ผู้สอน (เว้นว่างได้ ถ้ายังไม่กำหนด): ", allow_empty=True, default="").strip()

    if id_exists(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE, course_id):
        print(f"มี Course ID {course_id} ในระบบอยู่แล้ว (สถานะ Active) ห้ามซ้ำ!\n")
        return

    for r in read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE):
        if r[6] == 1 and decode_str(r[1]).strip().lower() == code.strip().lower():
            print(f"รายวิชารหัส '{code}' มีอยู่แล้วในระบบ ห้ามซ้ำ!\n")
            return

    code_bytes = encode_fixed(code, 15)
    title_bytes = encode_fixed(title, 50)
    cat_bytes = encode_fixed(category, 20)
    instructor_bytes = encode_fixed(instructor, 60)

    packed_data = struct.pack(COURSE_FORMAT, course_id, code_bytes, title_bytes, cat_bytes,
                               credits, fee, 1, 0, instructor_bytes)
    reused = write_record(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE, packed_data, 6)
    log_action(f"เพิ่มรายวิชา ID={course_id} ชื่อ={title}"
               + (" [ใช้ช่องว่างเดิมซ้ำ]" if reused else ""))
    print(f"บันทึกวิชา '{title}' เรียบร้อย!"
          + (" (นำช่องว่างจากข้อมูลที่ถูกลบกลับมาใช้ใหม่)" if reused else "") + "\n")


def update_course():
    print("\n--- แก้ไขข้อมูลรายวิชา ---")
    if not os.path.exists(COURSE_FILE) or os.path.getsize(COURSE_FILE) == 0:
        print("ยังไม่มีข้อมูลในระบบ\n")
        return
    search_id = ask_int("ป้อน Course ID ที่ต้องการแก้ไข: ")

    with open(COURSE_FILE, "r+b") as file:
        index = 0
        found = False
        while True:
            offset = index * COURSE_SIZE
            file.seek(offset)
            data_read = file.read(COURSE_SIZE)
            if not data_read:
                break
            unpacked = struct.unpack(COURSE_FORMAT, data_read)
            if unpacked[0] == search_id and unpacked[6] == 1:
                found = True
                curr_title = decode_str(unpacked[2])
                print(f"พบข้อมูลเดิม: {curr_title}")
                new_title = input("ชื่อวิชาใหม่ (Enter = ไม่เปลี่ยน): ") or curr_title
                new_fee = ask_float("ค่าธรรมเนียมใหม่ (Enter = ไม่เปลี่ยน): ", allow_empty=True, default=unpacked[5])
                full_str = input("สถานะเต็ม/ปิดรับ (0=เปิดรับ,1=เต็ม, Enter=ไม่เปลี่ยน): ")
                full_val = int(full_str) if full_str in ["0", "1"] else unpacked[7]

                t_bytes = encode_fixed(new_title, 50)
                packed_new = struct.pack(COURSE_FORMAT, unpacked[0], unpacked[1], t_bytes,
                                          unpacked[3], unpacked[4], new_fee, 1, full_val, unpacked[8])
                file.seek(offset)
                file.write(packed_new)
                log_action(f"แก้ไขรายวิชา ID={search_id}")
                print("แก้ไขข้อมูลเรียบร้อยแล้ว!\n")
                break
            index += 1
        if not found:
            print("ไม่พบวิชานี้ หรือถูกลบไปแล้ว\n")


def delete_course():
    print("\n--- ลบรายวิชา (Soft Delete) ---")
    if not os.path.exists(COURSE_FILE) or os.path.getsize(COURSE_FILE) == 0:
        print("ยังไม่มีข้อมูลในระบบ\n")
        return
    search_id = ask_int("ป้อน Course ID ที่ต้องการลบ: ")

    with open(COURSE_FILE, "r+b") as file:
        index = 0
        found = False
        while True:
            offset = index * COURSE_SIZE
            file.seek(offset)
            data_read = file.read(COURSE_SIZE)
            if not data_read:
                break
            unpacked = struct.unpack(COURSE_FORMAT, data_read)
            if unpacked[0] == search_id and unpacked[6] == 1:
                found = True
                packed_del = struct.pack(COURSE_FORMAT, unpacked[0], unpacked[1], unpacked[2],
                                          unpacked[3], unpacked[4], unpacked[5], 0, unpacked[7], unpacked[8])
                file.seek(offset)
                file.write(packed_del)
                log_action(f"ลบรายวิชา ID={search_id}")
                print(f"ลบวิชารหัส {search_id} เรียบร้อยแล้ว (Soft Delete)!\n")
                break
            index += 1
        if not found:
            print("ไม่พบวิชานี้\n")


def view_courses():
    print("\n--- เมนูย่อย: ดูข้อมูลรายวิชา ---")
    print("1) ดูทั้งหมด")
    print("2) ดูรายการเดียว (ตาม ID)")
    print("3) ดูแบบกรอง (ตามหมวดวิชา)")
    print("4) สถิติโดยสรุป")
    choice = input("เลือก: ").strip()
    records = read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE)
    active = [r for r in records if r[6] == 1]

    def fmt_line(r):
        full = "เต็ม/ปิดรับ" if r[7] == 1 else "เปิดรับ"
        instructor = decode_str(r[8]) or "(ยังไม่มีอาจารย์สอน)"
        return (f"ID:{r[0]} รหัส:{decode_str(r[1])} วิชา:{decode_str(r[2])} "
                f"หมวด:{decode_str(r[3])} {r[4]} หน่วยกิต ค่าวิชา:{r[5]:.2f} สถานะ:{full} "
                f"ผู้สอน:{instructor}")

    if choice == "1":
        if not active:
            print("ไม่มีรายวิชา (Active)\n")
            return
        for i, r in enumerate(active, 1):
            print(f"[{i}] {fmt_line(r)}")
    elif choice == "2":
        cid = ask_int("ป้อน Course ID: ")
        found = [r for r in active if r[0] == cid]
        print(fmt_line(found[0]) if found else "ไม่พบรายวิชานี้")
    elif choice == "3":
        kw = input("ป้อนคำค้นหมวดวิชา: ").strip().lower()
        found = [r for r in active if kw in decode_str(r[3]).lower()]
        if not found:
            print("ไม่พบรายวิชาที่ตรงเงื่อนไข")
        for r in found:
            print(fmt_line(r))
    elif choice == "4":
        fees = [r[5] for r in active] or [0.0]
        print(f"จำนวนรายวิชาทั้งหมด (records) : {len(records)}")
        print(f"จำนวนรายวิชา Active            : {len(active)}")
        print(f"จำนวนรายวิชาที่ถูกลบ            : {len(records) - len(active)}")
        print(f"ค่าธรรมเนียม ต่ำสุด/สูงสุด/เฉลี่ย : {min(fees):.2f} / {max(fees):.2f} / {sum(fees)/len(fees):.2f}")
    else:
        print("เลือกเมนูไม่ถูกต้อง")
    print()


# ============================================================
#  3) การลงทะเบียน (Enrollment)
# ============================================================

def _next_enroll_id():
    records = read_all_records(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE)
    return (max((r[0] for r in records), default=0)) + 1


def get_total_credits(student_code, exclude_enroll_id=None):
    """
    รวมหน่วยกิตทั้งหมดที่นักศึกษาคนนี้ลงทะเบียนอยู่ (เฉพาะรายการ Active)
    exclude_enroll_id: ใช้ตอนเปลี่ยนวิชา เพื่อไม่นับรายการเดิมที่กำลังจะถูกแทนที่
    """
    credit_map = {
        c[0]: c[4]
        for c in read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE)
    }
    total = 0
    for r in read_all_records(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE):
        if r[4] != 1 or decode_str(r[1]) != student_code:
            continue
        if exclude_enroll_id is not None and r[0] == exclude_enroll_id:
            continue
        total += credit_map.get(r[2], 0)
    return total


def view_available_courses():
    print("\n--- วิชาที่เปิดให้ลงทะเบียนได้ ---")
    courses = read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE)
    available = [c for c in courses if c[6] == 1 and c[7] == 0]
    if not available:
        print("ไม่มีวิชาที่เปิดให้ลงทะเบียนในขณะนี้\n")
        return
    for i, c in enumerate(available, 1):
        print(f"[{i}] Course ID    : {c[0]}")
        print(f"    รหัสวิชา     : {decode_str(c[1])}")
        print(f"    ชื่อวิชา     : {decode_str(c[2])}")
        print(f"    หมวดวิชา     : {decode_str(c[3])}")
        print(f"    หน่วยกิต     : {c[4]}")
        print(f"    ค่าธรรมเนียม : {c[5]:.2f} บาท")
        print()


def enroll_student():
    print("\n--- ลงทะเบียนเรียน ---")
    student_code = ask_student_code("ป้อนรหัสนักศึกษา 13 หลัก: ", check_duplicate=False)
    student = find_student_by_code(student_code)

    if not student:
        print("ไม่พบนักศึกษารหัสนี้ในระบบ (หรือถูกลบไปแล้ว)\n")
        return

    print(f"นักศึกษา: {decode_str(student[2])} (สาขา: {decode_str(student[3])})")
    current = get_total_credits(student_code)
    print(f"หน่วยกิตที่ลงทะเบียนอยู่แล้ว: {current}/{MAX_CREDITS_PER_STUDENT} หน่วยกิต")
    course_id = ask_int("ป้อน Course ID ที่ต้องการลงทะเบียน: ")

    course_rec = None
    for r in read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE):
        if r[0] == course_id and r[6] == 1:
            course_rec = r
            break
    if course_rec is None:
        print("ไม่พบรายวิชานี้ในระบบ (หรือถูกลบไปแล้ว)\n")
        return
    if course_rec[7] == 1:
        print("วิชานี้เต็ม/ปิดรับลงทะเบียนแล้ว\n")
        return

    # ตรวจสอบการลงทะเบียนซ้ำ
    for r in read_all_records(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE):
        if decode_str(r[1]) == student_code and r[2] == course_id and r[4] == 1:
            print("นักศึกษาคนนี้ลงทะเบียนวิชานี้อยู่แล้ว\n")
            return

    # ตรวจสอบหน่วยกิตรวมไม่ให้เกินเพดานที่มหาวิทยาลัยกำหนด
    current_credits = get_total_credits(student_code)
    new_total = current_credits + course_rec[4]
    if new_total > MAX_CREDITS_PER_STUDENT:
        print(f"ลงทะเบียนไม่ได้! หน่วยกิตรวมจะเกินเพดานที่กำหนด")
        print(f"  ลงทะเบียนอยู่แล้ว : {current_credits} หน่วยกิต")
        print(f"  วิชานี้           : {course_rec[4]} หน่วยกิต")
        print(f"  รวมจะเป็น         : {new_total} หน่วยกิต (เพดาน {MAX_CREDITS_PER_STUDENT} หน่วยกิต)\n")
        return

    enroll_id = _next_enroll_id()
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_bytes = encode_fixed(date_str, 20)
    code_bytes = encode_fixed(student_code, 15)

    packed = struct.pack(ENROLL_FORMAT, enroll_id, code_bytes, course_id, date_bytes, 1)
    reused = write_record(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE, packed, 4)
    log_action(f"ลงทะเบียน StudentCode={student_code} -> Course={course_id} (EnrollID={enroll_id})"
               + (" [ใช้ช่องว่างเดิมซ้ำ]" if reused else ""))
    print(f"ลงทะเบียนเรียบร้อย! (Enrollment ID: {enroll_id})"
          + (" (นำช่องว่างจากข้อมูลที่ถูกยกเลิกกลับมาใช้ใหม่)" if reused else "") + "\n")


def _get_active_enrollments_by_student(student_code):
    """คืนรายการลงทะเบียน Active ของ StudentCode พร้อมลำดับสำหรับให้ผู้ใช้เลือก"""
    records = read_all_records(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE)
    return [r for r in records if r[4] == 1 and decode_str(r[1]) == student_code]


def _show_student_enrollment_choices(student_code):
    """แสดงวิชาที่นักศึกษาลงทะเบียนอยู่ และคืนรายการตามลำดับ 1..n"""
    enrollments = _get_active_enrollments_by_student(student_code)
    if not enrollments:
        print("ไม่พบรายการลงทะเบียนที่ยัง Active ของ StudentCode นี้\n")
        return []

    courses = {
        c[0]: c for c in read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE)
    }
    print(f"\nรายการวิชาที่ลงทะเบียนของ StudentCode: {student_code}")
    for i, r in enumerate(enrollments, 1):
        c = courses.get(r[2])
        code = decode_str(c[1]) if c else "-"
        title = decode_str(c[2]) if c else "(ไม่พบวิชา)"
        print(f"  {i}) Course ID {r[2]} | {code} - {title}")
    print("  0) ยกเลิกการทำรายการ")
    return enrollments


def _ask_enrollment_by_student(student_code, action_text):
    """ให้เลือก Enrollment จากรายการของ StudentCode โดยไม่ต้องจำ Enrollment ID"""
    enrollments = _show_student_enrollment_choices(student_code)
    if not enrollments:
        return None

    while True:
        choice = input(f"เลือกวิชาที่ต้องการ{action_text} (0 = ยกเลิก): ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(enrollments):
            return enrollments[int(choice) - 1]
        print("เลือกหมายเลขรายการไม่ถูกต้อง กรุณาลองใหม่")


def change_enrollment():
    """เปลี่ยนวิชาที่ลงทะเบียน โดยค้นด้วย StudentCode แล้วเลือกจากรายการ"""
    print("\n--- เปลี่ยนวิชาที่ลงทะเบียน ---")
    if not os.path.exists(ENROLL_FILE) or os.path.getsize(ENROLL_FILE) == 0:
        print("ยังไม่มีข้อมูลการลงทะเบียนในระบบ\n")
        return

    student_code = ask_student_code("ป้อน StudentCode 13 หลัก: ", check_duplicate=False)
    student = find_student_by_code(student_code)
    if not student:
        print("ไม่พบนักศึกษารหัสนี้ในระบบ (หรือถูกลบไปแล้ว)\n")
        return

    selected = _ask_enrollment_by_student(student_code, "เปลี่ยน")
    if selected is None:
        print("ยกเลิกการทำรายการ\n")
        return

    search_id = selected[0]
    old_course_id = selected[2]
    courses = read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE)
    old_course = next((c for c in courses if c[0] == old_course_id), None)
    old_title = decode_str(old_course[2]) if old_course else "(ไม่พบวิชา)"
    print(f"\nวิชาปัจจุบัน: Course ID {old_course_id} - {old_title}")

    available = [c for c in courses if c[6] == 1 and c[7] == 0 and c[0] != old_course_id]
    if not available:
        print("ไม่มีวิชาอื่นที่เปิดให้เปลี่ยนในขณะนี้\n")
        return

    print("\n--- วิชาที่เปิดให้เปลี่ยน ---")
    for i, c in enumerate(available, 1):
        print(f"  {i}) Course ID {c[0]} | {decode_str(c[1])} - {decode_str(c[2])} | {c[4]} หน่วยกิต")
    print("  0) ยกเลิกการทำรายการ")

    while True:
        choice = input("เลือกวิชาใหม่: ").strip()
        if choice == "0":
            print("ยกเลิกการทำรายการ\n")
            return
        if choice.isdigit() and 1 <= int(choice) <= len(available):
            new_course_rec = available[int(choice) - 1]
            break
        print("เลือกหมายเลขรายการไม่ถูกต้อง กรุณาลองใหม่")

    new_course_id = new_course_rec[0]

    # กันลงทะเบียนซ้ำวิชาเดียวกันที่มีอยู่แล้ว
    for r in read_all_records(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE):
        if decode_str(r[1]) == student_code and r[2] == new_course_id and r[4] == 1:
            print("นักศึกษาคนนี้ลงทะเบียนวิชาใหม่อยู่แล้ว\n")
            return

    # ตรวจสอบหน่วยกิตรวม โดยไม่นับวิชาเดิมที่กำลังถูกแทนที่
    other_credits = get_total_credits(student_code, exclude_enroll_id=search_id)
    new_total = other_credits + new_course_rec[4]
    if new_total > MAX_CREDITS_PER_STUDENT:
        print("เปลี่ยนวิชาไม่ได้! หน่วยกิตรวมจะเกินเพดานที่กำหนด")
        print(f"  วิชาอื่นที่ลงอยู่ : {other_credits} หน่วยกิต")
        print(f"  วิชาใหม่          : {new_course_rec[4]} หน่วยกิต")
        print(f"  รวมจะเป็น         : {new_total} หน่วยกิต (เพดาน {MAX_CREDITS_PER_STUDENT} หน่วยกิต)\n")
        return

    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_bytes = encode_fixed(date_str, 20)
    packed_new = struct.pack(ENROLL_FORMAT, selected[0], selected[1], new_course_id, date_bytes, 1)

    with open(ENROLL_FILE, "r+b") as f:
        offset = selected[0]  # placeholder; locate by record index below
        records = read_all_records(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE)
        record_index = next(i for i, r in enumerate(records) if r[0] == search_id and r[4] == 1)
        f.seek(record_index * ENROLL_SIZE)
        f.write(packed_new)

    log_action(f"เปลี่ยนวิชาลงทะเบียน EnrollID={search_id} StudentCode={student_code} Course {old_course_id} -> {new_course_id}")
    print(f"เปลี่ยนวิชาเรียบร้อยแล้ว! {old_course_id} -> {new_course_id}\n")


def cancel_enrollment():
    """ยกเลิกการลงทะเบียน โดยค้นด้วย StudentCode แล้วเลือกวิชาจากรายการ"""
    print("\n--- ยกเลิกการลงทะเบียน (Soft Delete) ---")
    if not os.path.exists(ENROLL_FILE) or os.path.getsize(ENROLL_FILE) == 0:
        print("ยังไม่มีข้อมูลการลงทะเบียนในระบบ\n")
        return

    student_code = ask_student_code("ป้อน StudentCode 13 หลัก: ", check_duplicate=False)
    student = find_student_by_code(student_code)
    if not student:
        print("ไม่พบนักศึกษารหัสนี้ในระบบ (หรือถูกลบไปแล้ว)\n")
        return

    selected = _ask_enrollment_by_student(student_code, "ยกเลิก")
    if selected is None:
        print("ยกเลิกการทำรายการ\n")
        return

    search_id = selected[0]
    course_id = selected[2]
    courses = read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE)
    course = next((c for c in courses if c[0] == course_id), None)
    course_name = decode_str(course[2]) if course else "(ไม่พบวิชา)"

    confirm = input(f"ยืนยันยกเลิก {decode_str(course[1]) if course else course_id} - {course_name} ? (Y/N): ").strip().upper()
    if confirm != "Y":
        print("ยกเลิกการทำรายการ\n")
        return

    records = read_all_records(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE)
    record_index = next((i for i, r in enumerate(records) if r[0] == search_id and r[4] == 1), None)
    if record_index is None:
        print("ไม่พบรายการลงทะเบียนนี้ หรือถูกยกเลิกไปแล้ว\n")
        return

    u = records[record_index]
    packed_del = struct.pack(ENROLL_FORMAT, u[0], u[1], u[2], u[3], 0)
    with open(ENROLL_FILE, "r+b") as f:
        f.seek(record_index * ENROLL_SIZE)
        f.write(packed_del)

    log_action(f"ยกเลิกการลงทะเบียน EnrollID={search_id} StudentCode={student_code} Course={course_id}")
    print("ยกเลิกการลงทะเบียนเรียบร้อยแล้ว!\n")

def view_enrollments():
    print("\n--- เมนูย่อย: ดูข้อมูลการลงทะเบียน ---")
    print("1) ดูทั้งหมด")
    print("2) ดูตามรหัสนักศึกษา 13 หลัก")
    print("3) ดูตาม Student ID / ปีการศึกษา (แสดงทุกคนในกลุ่ม)")
    print("4) ดูตาม Course ID")
    print("5) สถิติโดยสรุป")
    choice = input("เลือก: ").strip()

    records = read_all_records(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE)
    active = [r for r in records if r[4] == 1]
    
    # สร้าง Map นักศึกษาแบบ {student_code: student_name}
    student_map = {
        decode_str(r[1]): decode_str(r[2]) 
        for r in read_all_records(STUDENT_FILE, STUDENT_FORMAT, STUDENT_SIZE)
    }
    course_map = {
        r[0]: decode_str(r[2]) 
        for r in read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE)
    }

    def print_block(i, r):
        code_str = decode_str(r[1])
        sname = student_map.get(code_str, "(ไม่พบนักศึกษา)")
        cname = course_map.get(r[2], "(ไม่พบวิชา)")
        status = "Active" if r[4] == 1 else "Cancelled"
        print(f"[{i}] Enrollment ID   : {r[0]}")
        print(f"    Student         : {code_str} - {sname}")
        print(f"    Course          : {r[2]} - {cname}")
        print(f"    วันที่ลงทะเบียน : {decode_str(r[3])}")
        print(f"    สถานะ           : {status}")
        print()

    if choice == "1":
        if not active:
            print("ไม่มีข้อมูลการลงทะเบียน (Active)\n")
            return
        for i, r in enumerate(active, 1):
            print_block(i, r)
    elif choice == "2":
        code = ask_student_code("ป้อนรหัสนักศึกษา 13 หลัก: ", check_duplicate=False)
        found = [r for r in active if decode_str(r[1]) == code]
        if not found:
            print("ไม่พบข้อมูลการลงทะเบียนของนักศึกษารหัสนี้")
        for i, r in enumerate(found, 1):
            print_block(i, r)
    elif choice == "3":
        sid = ask_int("ป้อน Student ID / ปีการศึกษา: ")
        # ค้นหารหัสนักศึกษาทั้งหมดที่มี student_id เท่ากับ sid
        matching_codes = [
            decode_str(r[1]) 
            for r in read_all_records(STUDENT_FILE, STUDENT_FORMAT, STUDENT_SIZE) 
            if r[0] == sid
        ]
        found = [r for r in active if decode_str(r[1]) in matching_codes]
        if not found:
            print(f"ไม่พบข้อมูลการลงทะเบียนของกลุ่ม ID/ปี {sid}")
        for i, r in enumerate(found, 1):
            print_block(i, r)
    elif choice == "4":
        cid = ask_int("ป้อน Course ID: ")
        found = [r for r in active if r[2] == cid]
        if not found:
            print("ไม่พบข้อมูลการลงทะเบียนของวิชานี้")
        for i, r in enumerate(found, 1):
            print_block(i, r)
    elif choice == "5":
        print(f"จำนวนการลงทะเบียนทั้งหมด (records) : {len(records)}")
        print(f"จำนวนที่ยังลงทะเบียนอยู่ (Active)    : {len(active)}")
        print(f"จำนวนที่ถูกยกเลิก                    : {len(records) - len(active)}")
    else:
        print("เลือกเมนูไม่ถูกต้อง")
    print()


# ============================================================
#  4) สร้างรายงานสรุป
# ============================================================

def display_width(text):
    """
    คำนวณความกว้างสำหรับแสดงผล
    - ตัวอักษรทั่วไป = 1
    - อักขระ combining / mark = 0
    """
    import unicodedata

    text = str(text)
    width = 0

    for ch in text:
        category = unicodedata.category(ch)

        if category in ("Mn", "Me", "Cf"):
            continue

        width += 1

    return width


def pad_text(text, width):
    """
    เติมช่องว่างให้ข้อความมีความกว้างตามที่กำหนด
    โดยไม่ตัดข้อความทิ้ง
    """
    text = str(text)
    current_width = display_width(text)

    if current_width >= width:
        return text

    return text + " " * (width - current_width)


# ============================================================
# Report 1
# ============================================================

def generate_report1():
    """Report 1: รายชื่อวิชาทั้งหมดและจำนวนหน่วยกิต"""

    courses = [
        c
        for c in read_all_records(
            COURSE_FILE,
            COURSE_FORMAT,
            COURSE_SIZE
        )
        if c[6] == 1
    ]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = "report1_courses.txt"

    # ความกว้างของแต่ละ column
    NO_W = 4
    ID_W = 10
    CODE_W = 15
    NAME_W = 38
    CREDIT_W = 7
    INSTRUCTOR_W = 45

    # ความกว้างรวมของตาราง
    TABLE_W = (
        NO_W
        + ID_W
        + CODE_W
        + NAME_W
        + CREDIT_W
        + INSTRUCTOR_W
        + 14
    )

    with open(filename, "w", encoding="utf-8") as f:

        f.write("=" * TABLE_W + "\n")
        f.write("COURSE REGISTRATION SYSTEM - REPORT 1\n")
        f.write("รายงานรายวิชาและจำนวนหน่วยกิต\n")
        f.write(f"Generated At : {now}\n")
        f.write("=" * TABLE_W + "\n\n")

        # Header
        f.write(
            f"| {'No.':<{NO_W}} "
            f"| {'Course ID':<{ID_W}} "
            f"| {'Course Code':<{CODE_W}} "
            f"| {'Course Name':<{NAME_W}} "
            f"| {'Credits':<{CREDIT_W}} "
            f"| {'Instructor':<{INSTRUCTOR_W}} |\n"
        )

        f.write("-" * TABLE_W + "\n")

        for i, c in enumerate(courses, 1):

            code = decode_str(c[1]).strip()
            name = decode_str(c[2]).strip()
            inst = decode_str(c[8]).strip()

            if not inst:
                inst = "(ยังไม่มีอาจารย์สอน)"

            # สำคัญ:
            # ไม่มี [:22] / [:25] / [:40]
            # ข้อมูลชื่อจะไม่ถูกตัด
            row = (
                f"| {str(i):<{NO_W}} "
                f"| {str(c[0]):<{ID_W}} "
                f"| {pad_text(code, CODE_W)} "
                f"| {pad_text(name, NAME_W)} "
                f"| {str(c[4]):<{CREDIT_W}} "
                f"| {pad_text(inst, INSTRUCTOR_W)} |"
            )

            f.write(row + "\n")

        f.write("-" * TABLE_W + "\n")
        f.write(f"Total Active Courses  : {len(courses)}\n")
        f.write(
            f"Total Credits         : "
            f"{sum(c[4] for c in courses)}\n"
        )

    log_action(f"สร้าง Report 1 -> {filename}")
    print(f"สร้าง {filename} เรียบร้อยแล้ว!\n")


# ============================================================
# Report 2
# ============================================================

def generate_report2():
    """Report 2: รายงานการลงทะเบียนของนักศึกษาทั้งหมดในไฟล์เดียว"""

    students = [
        s
        for s in read_all_records(
            STUDENT_FILE,
            STUDENT_FORMAT,
            STUDENT_SIZE
        )
        if s[5] == 1
    ]

    courses = {
        c[0]: c
        for c in read_all_records(
            COURSE_FILE,
            COURSE_FORMAT,
            COURSE_SIZE
        )
    }

    enrolls = read_all_records(
        ENROLL_FILE,
        ENROLL_FORMAT,
        ENROLL_SIZE
    )

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = "report2_students.txt"

    # ความกว้างของตาราง
    NO_W = 4
    ID_W = 10
    NAME_W = 35
    INSTRUCTOR_W = 45
    CREDIT_W = 7
    STATUS_W = 10

    TABLE_W = (
        NO_W
        + ID_W
        + NAME_W
        + INSTRUCTOR_W
        + CREDIT_W
        + STATUS_W
        + 14
    )

    with open(filename, "w", encoding="utf-8") as f:

        f.write("=" * TABLE_W + "\n")
        f.write(
            "COURSE REGISTRATION SYSTEM - REPORT 2\n"
        )
        f.write(
            "รายงานการลงทะเบียนของนักศึกษาทั้งหมด\n"
        )
        f.write(f"Generated At : {now}\n")
        f.write("=" * TABLE_W + "\n\n")

        if not students:
            f.write("ไม่มีข้อมูลนักศึกษา Active\n")

        for i, student in enumerate(students, 1):

            code = decode_str(student[1]).strip()
            name = decode_str(student[2]).strip()
            major = decode_str(student[3]).strip()
            year = student[4]

            es = [
                e
                for e in enrolls
                if decode_str(e[1]).strip() == code
            ]

            active = [
                e for e in es
                if e[4] == 1
            ]

            dropped = [
                e for e in es
                if e[4] == 0
            ]

            ac = sum(
                courses[e[2]][4]
                for e in active
                if e[2] in courses
            )

            dc = sum(
                courses[e[2]][4]
                for e in dropped
                if e[2] in courses
            )

            rem = max(
                0,
                MAX_CREDITS_PER_STUDENT - ac
            )

            f.write("=" * TABLE_W + "\n")
            f.write(f"STUDENT #{i}\n")
            f.write(f"Student Code : {code}\n")
            f.write(f"Name         : {name}\n")
            f.write(f"Major        : {major}\n")
            f.write(f"Year         : {year}\n")
            f.write("-" * TABLE_W + "\n\n")

            f.write("Enrolled Courses\n")
            f.write("-" * TABLE_W + "\n")

            # Header
            f.write(
                f"| {'No.':<{NO_W}} "
                f"| {'Course ID':<{ID_W}} "
                f"| {'Course Name':<{NAME_W}} "
                f"| {'Instructor':<{INSTRUCTOR_W}} "
                f"| {'Credits':<{CREDIT_W}} "
                f"| {'Status':<{STATUS_W}} |\n"
            )

            f.write("-" * TABLE_W + "\n")

            if es:

                for no, e in enumerate(es, 1):

                    c = courses.get(e[2])

                    if not c:
                        continue

                    course_name = decode_str(c[2]).strip()
                    inst = decode_str(c[8]).strip()

                    if not inst:
                        inst = "(ยังไม่มีอาจารย์สอน)"

                    status = (
                        "Active"
                        if e[4] == 1
                        else "Dropped"
                    )

                    row = (
                        f"| {str(no):<{NO_W}} "
                        f"| {str(c[0]):<{ID_W}} "
                        f"| {pad_text(course_name, NAME_W)} "
                        f"| {pad_text(inst, INSTRUCTOR_W)} "
                        f"| {str(c[4]):<{CREDIT_W}} "
                        f"| {status:<{STATUS_W}} |"
                    )

                    f.write(row + "\n")

            else:
                f.write("| ไม่มีประวัติการลงทะเบียน\n")

            f.write("-" * TABLE_W + "\n")

            f.write(
                f"Active Courses   : {len(active)}\n"
            )
            f.write(
                f"Dropped Courses  : {len(dropped)}\n"
            )
            f.write(
                f"Active Credits   : {ac}\n"
            )
            f.write(
                f"Dropped Credits  : {dc}\n"
            )
            f.write(
                f"Remaining Credits: {rem}\n"
            )
            f.write(
                f"Credit Limit     : "
                f"{MAX_CREDITS_PER_STUDENT}\n\n"
            )

    log_action(f"สร้าง Report 2 -> {filename}")
    print(f"สร้าง {filename} เรียบร้อยแล้ว!\n")


# ============================================================
# Report 3
# ============================================================

def generate_report3():
    """Report 3: รายงานของอาจารย์ทุกคนและนักศึกษาที่ลงทะเบียนในแต่ละวิชา"""

    courses = [
        c
        for c in read_all_records(
            COURSE_FILE,
            COURSE_FORMAT,
            COURSE_SIZE
        )
        if c[6] == 1
    ]

    enrolls = read_all_records(
        ENROLL_FILE,
        ENROLL_FORMAT,
        ENROLL_SIZE
    )

    students = {
        decode_str(s[1]).strip(): s
        for s in read_all_records(
            STUDENT_FILE,
            STUDENT_FORMAT,
            STUDENT_SIZE
        )
        if s[5] == 1
    }

    now = datetime.datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    groups = {}

    for c in courses:

        instructor = decode_str(c[8]).strip()

        if not instructor:
            instructor = "(ยังไม่มีอาจารย์สอน)"

        groups.setdefault(
            instructor,
            []
        ).append(c)

    filename = "report3_instructors.txt"

    with open(filename, "w", encoding="utf-8") as f:

        f.write("=" * 110 + "\n")
        f.write(
            "COURSE REGISTRATION SYSTEM - REPORT 3\n"
        )
        f.write(
            "รายงานรายวิชาของอาจารย์ทุกคนและนักศึกษาที่ลงทะเบียน\n"
        )
        f.write(f"Generated At : {now}\n")
        f.write("=" * 110 + "\n\n")

        if not groups:
            f.write("ไม่มีข้อมูลรายวิชา Active\n")

        for inst, clist in groups.items():

            f.write("=" * 110 + "\n")
            f.write(f"INSTRUCTOR: {inst}\n")
            f.write("=" * 110 + "\n\n")

            for c in clist:

                es = [
                    e
                    for e in enrolls
                    if e[2] == c[0]
                ]

                active = sum(
                    e[4] == 1
                    for e in es
                )

                dropped = sum(
                    e[4] == 0
                    for e in es
                )

                f.write(
                    f"Course ID   : {c[0]}\n"
                    f"Course Code : {decode_str(c[1]).strip()}\n"
                    f"Course Name : {decode_str(c[2]).strip()}\n"
                    f"Credits     : {c[4]}\n\n"
                )

                f.write("Enrolled Students\n")
                f.write("-" * 90 + "\n")

                f.write(
                    f"| {'No.':<4} | "
                    f"{'Student Code':<15} | "
                    f"{'Name':<40} | "
                    f"{'Status':<10} |\n"
                )

                f.write("-" * 90 + "\n")

                if es:

                    for no, e in enumerate(es, 1):

                        st = students.get(
                            decode_str(e[1]).strip()
                        )

                        if st:
                            sn = decode_str(
                                st[2]
                            ).strip()
                        else:
                            sn = "(ไม่พบนักศึกษา Active)"

                        status = (
                            "Active"
                            if e[4] == 1
                            else "Dropped"
                        )

                        f.write(
                            f"| {no:<4} | "
                            f"{decode_str(e[1]).strip():<15} | "
                            f"{pad_text(sn, 40)} | "
                            f"{status:<10} |\n"
                        )

                else:
                    f.write(
                        "| ไม่มีนักศึกษาลงทะเบียน\n"
                    )

                f.write("-" * 90 + "\n")
                f.write(
                    f"Active Students  : {active}\n"
                )
                f.write(
                    f"Dropped Students : {dropped}\n"
                )
                f.write(
                    f"Total Records    : "
                    f"{active + dropped}\n\n"
                )

    log_action(f"สร้าง Report 3 -> {filename}")
    print(f"สร้าง {filename} เรียบร้อยแล้ว!\n")


# ============================================================
# สร้าง Report ทั้งหมด
# ============================================================

def generate_all_reports():
    """สร้าง Report 1-3 อัตโนมัติ โดยไม่ต้องถามข้อมูลเพิ่ม"""

    generate_report1()
    generate_report2()
    generate_report3()


# ============================================================
# Report Menu
# ============================================================

def report_menu():
    """เมนูสร้างรายงาน 3 แบบ แยกไฟล์ชัดเจน"""

    while True:

        print("\n---- สร้างรายงาน (Generate Reports) ----")
        print("1) Report 1 - รายชื่อวิชา")
        print("2) Report 2 - รายงานของนักศึกษาทั้งหมด")
        print("3) Report 3 - รายงานของอาจารย์ทั้งหมด")
        print("0) กลับเมนูอาจารย์")

        c = input("เลือก: ").strip()

        if c == "1":
            generate_report1()

        elif c == "2":
            generate_report2()

        elif c == "3":
            generate_report3()

        elif c == "0":
            break

        else:
            print("เลือกเมนูไม่ถูกต้อง\n")



# ============================================================
#  วิชาตั้งต้น (Preset Courses)
# ============================================================

DEFAULT_COURSES = [
    (1001, "060233101", "INTRO TO INFO & NETWORK ENG", "Core", 3, 1500.0,
     "Asst.Prof.Dr.NITIGAN NAKJUATONG"),

    (1002, "060233106", "INFO & NETWORK ENG DRAWING", "Core", 3, 1500.0,
     "Ajarn.KAROON INTAWAD"),

    (1003, "060233112", "DATA ENGINEERING", "Core", 3, 1500.0,
     "Asst.Prof.Dr.SARAYOOT TANESSAKULWATTANA"),

    (1004, "060233114", "STAT FOR DATA ENG & SCIENTISTS", "Core", 3, 1300.0,
     "Ajarn Dr.KARN NA SRITHA"),

    (1005, "060233115", "COMPUTER PROGRAMMING", "Core", 3, 1500.0,
     "Assoc.Prof.Dr.ANIRACH MINGKHWAN"),

    (1006, "060233118", "SOFTWARE ENGINEERING", "Core", 3, 1500.0,
     "Asst.Prof.Dr.SUPEETI KULCHAN"),

    (1007, "060233205", "ADVANCED NETWORK & PROTOCOL", "Core", 3, 1500.0,
     "Asst.Prof.Dr.KHANISTA NAMEE"),

    (1008, "060233211", "CLOUD ARCHITECTURE AND APPLICATIONS", "Core", 3, 1500.0,
     "Asst.Prof.Dr.SARAYOOT TANESSAKULWATTANA"),

    (1009, "060233212", "BIG DATA ANALYTICS", "Core", 3, 1500.0,
     "Ajarn Dr.SIRINTRA VAIWSRI"),

    (1010, "060233214", "INFOR & NETW ENGR SEMINAR", "Core", 1, 500.0,
     "Asst.Prof.Dr.NITIGAN NAKJUATONG"),
]


def seed_default_courses():
    """
    สร้างวิชาตั้งต้นพร้อมอาจารย์ผู้สอนอัตโนมัติ

    - ถ้า courses.dat ยังไม่มีข้อมูล -> เพิ่ม DEFAULT_COURSES ทั้งหมด
    - ถ้ามีข้อมูลอยู่แล้ว -> เพิ่มเฉพาะวิชาที่รหัสวิชายังไม่มี
    - ไม่สร้างวิชาซ้ำ
    - ชื่ออาจารย์จะถูกบันทึกลงใน courses.dat ตั้งแต่เริ่มต้น
    """
    existing_courses = read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE)

    existing_codes = {
        decode_str(r[1]).strip().lower()
        for r in existing_courses
        if r[6] == 1
    }

    existing_ids = {
        r[0]
        for r in existing_courses
        if r[6] == 1
    }

    courses_to_add = []

    for course in DEFAULT_COURSES:
        course_id, code, title, category, credits, fee, instructor = course

        # ป้องกัน Course ID หรือรหัสวิชาซ้ำ
        if course_id in existing_ids:
            continue

        if code.strip().lower() in existing_codes:
            continue

        courses_to_add.append(course)

    if not courses_to_add:
        return

    with open(COURSE_FILE, "ab") as f:
        for course_id, code, title, category, credits, fee, instructor in courses_to_add:
            code_b = encode_fixed(code, 15)
            title_b = encode_fixed(title, 50)
            cat_b = encode_fixed(category, 20)
            instructor_b = encode_fixed(instructor, 60)

            packed = struct.pack(
                COURSE_FORMAT,
                course_id,
                code_b,
                title_b,
                cat_b,
                credits,
                fee,
                1,  # Active
                0,  # ยังไม่เต็ม
                instructor_b
            )
            f.write(packed)

    log_action(
        f"เพิ่มวิชาตั้งต้น {len(courses_to_add)} วิชา พร้อมอาจารย์ผู้สอนอัตโนมัติ"
    )


# ============================================================
#  5) อาจารย์ผู้สอน (Instructor) -- เลือกวิชาที่จะสอน
#  แนวคิด: ไม่สร้างไฟล์ที่ 4 เพราะโจทย์กำหนดตายตัวว่าใช้ได้ 3 ไฟล์
#  จึงเก็บชื่ออาจารย์ไว้เป็นฟิลด์หนึ่งในตัว record ของ courses.dat แทน
# ============================================================

def assign_instructor():
    """ให้อาจารย์เลือกวิชาที่จะสอน (กำหนด/เปลี่ยนชื่ออาจารย์ผู้สอนของวิชา)"""
    print("\n--- เลือกวิชาที่จะสอน ---")
    if not os.path.exists(COURSE_FILE) or os.path.getsize(COURSE_FILE) == 0:
        print("ยังไม่มีข้อมูลรายวิชาในระบบ\n")
        return

    instructor_name = input("ป้อนชื่ออาจารย์ผู้สอน: ").strip()
    if not instructor_name:
        print("กรุณาป้อนชื่ออาจารย์\n")
        return

    # แสดงวิชาที่ยัง Active ให้เลือกก่อน
    active_courses = [c for c in read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE) if c[6] == 1]
    if not active_courses:
        print("ไม่มีรายวิชาที่เปิดใช้งานอยู่ในขณะนี้\n")
        return
    print("\nรายวิชาที่มีอยู่ในระบบ:")
    for c in active_courses:
        curr_instructor = decode_str(c[8]) or "(ยังไม่มีอาจารย์สอน)"
        print(f"  ID:{c[0]} | {decode_str(c[1])} - {decode_str(c[2])} | ผู้สอนปัจจุบัน: {curr_instructor}")

    course_id = ask_int("\nป้อน Course ID ที่ต้องการสอน: ")

    with open(COURSE_FILE, "r+b") as file:
        index = 0
        found = False
        while True:
            offset = index * COURSE_SIZE
            file.seek(offset)
            data_read = file.read(COURSE_SIZE)
            if not data_read:
                break
            unpacked = struct.unpack(COURSE_FORMAT, data_read)
            if unpacked[0] == course_id and unpacked[6] == 1:
                found = True
                old_instructor = decode_str(unpacked[8])
                instructor_bytes = encode_fixed(instructor_name, 60)
                packed_new = struct.pack(COURSE_FORMAT, unpacked[0], unpacked[1], unpacked[2],
                                          unpacked[3], unpacked[4], unpacked[5], unpacked[6],
                                          unpacked[7], instructor_bytes)
                file.seek(offset)
                file.write(packed_new)
                log_action(f"กำหนดอาจารย์ผู้สอน Course ID={course_id} -> {instructor_name}"
                           + (f" (เดิม: {old_instructor})" if old_instructor else ""))
                print(f"กำหนดให้ '{instructor_name}' เป็นผู้สอนวิชา ID {course_id} เรียบร้อยแล้ว!\n")
                break
            index += 1
        if not found:
            print("ไม่พบรายวิชานี้ในระบบ (หรือถูกลบไปแล้ว)\n")


def view_courses_by_instructor():
    """ดูว่าวิชาไหนมีอาจารย์คนไหนสอนบ้าง (ดูทั้งหมด หรือค้นหาตามชื่ออาจารย์)"""
    print("\n--- ดูรายวิชาแยกตามอาจารย์ผู้สอน ---")
    keyword = input("ป้อนชื่ออาจารย์ที่ต้องการค้นหา (เว้นว่าง = ดูทั้งหมด): ").strip().lower()
    courses = [c for c in read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE) if c[6] == 1]
    if not courses:
        print("ไม่มีรายวิชาที่เปิดใช้งานอยู่ในขณะนี้\n")
        return

    if keyword:
        courses = [c for c in courses if keyword in decode_str(c[8]).lower()]
        if not courses:
            print(f"ไม่พบวิชาที่มีอาจารย์ตรงกับคำค้น '{keyword}'\n")
            return

    for c in courses:
        instructor = decode_str(c[8]) or "(ยังไม่มีอาจารย์สอน)"
        print(f"[Course ID {c[0]}] {decode_str(c[1])} - {decode_str(c[2])} | ผู้สอน: {instructor}")
    print()


def instructor_menu():
    while True:
        print("\n---- อาจารย์ผู้สอน (Instructor) ----")
        print("1) เลือกวิชาที่จะสอน")
        print("2) ดูรายวิชาแยกตามอาจารย์ผู้สอน")
        print("0) กลับเมนูหลัก")
        c = input("เลือก: ").strip()
        if c == "1":
            assign_instructor()
        elif c == "2":
            view_courses_by_instructor()
        elif c == "0":
            break
        else:
            print("เลือกเมนูไม่ถูกต้อง\n")


# ============================================================
#  เมนูหลักและเมนูย่อย
# ============================================================

def course_menu():
    while True:
        print("\n---- จัดการรายวิชา (Courses) ----")
        print("1) เพิ่มรายวิชา")
        print("2) แก้ไขรายวิชา")
        print("3) ลบรายวิชา")
        print("4) ดูรายวิชา")
        print("0) กลับเมนูหลัก")
        c = input("เลือก: ").strip()
        if c == "1":
            add_course()
        elif c == "2":
            update_course()
        elif c == "3":
            delete_course()
        elif c == "4":
            view_courses()
        elif c == "0":
            break
        else:
            print("เลือกเมนูไม่ถูกต้อง\n")


def student_menu():
    while True:
        print("\n---- จัดการนักศึกษา (Students) ----")
        print("1) เพิ่มนักศึกษา")
        print("2) แก้ไขนักศึกษา")
        print("3) ลบนักศึกษา")
        print("4) ดูนักศึกษา")
        print("0) กลับเมนูหลัก")
        c = input("เลือก: ").strip()
        if c == "1":
            add_student()
        elif c == "2":
            update_student()
        elif c == "3":
            delete_student()
        elif c == "4":
            view_students()
        elif c == "0":
            break
        else:
            print("เลือกเมนูไม่ถูกต้อง\n")


def enrollment_menu():
    """เมนูการลงทะเบียนสำหรับ Instructor"""
    while True:
        print("\n---- การลงทะเบียนเรียน (Enrollments) ----")
        print("1) ลงทะเบียน")
        print("2) เปลี่ยนวิชาที่ลงทะเบียน")
        print("3) ยกเลิกการลงทะเบียน")
        print("4) ดูข้อมูลการลงทะเบียน")
        print("5) ดูวิชาที่เปิดให้ลงทะเบียน")
        print("0) กลับเมนูหลัก")
        c = input("เลือก: ").strip()
        if c == "1":
            enroll_student()
        elif c == "2":
            change_enrollment()
        elif c == "3":
            cancel_enrollment()
        elif c == "4":
            view_enrollments()
        elif c == "5":
            view_available_courses()
        elif c == "0":
            break
        else:
            print("เลือกเมนูไม่ถูกต้อง\n")


def student_enrollment_menu():
    """เมนูลงทะเบียนที่นักศึกษาเข้าถึงได้ตาม titit.txt"""
    enrollment_menu()


def student_portal():
    """เมนูสำหรับนักศึกษา: เข้าถึงเฉพาะการลงทะเบียนเรียน"""
    while True:
        print("\n==========================================")
        print(" ระบบลงทะเบียนเรียน (For Students) ")
        print("==========================================")
        print("1) การลงทะเบียนเรียน (Enrollments)")
        print("0) ออกจากโปรแกรม (Exit)")
        choice = input("เลือกเมนู (0-1): ").strip()
        if choice == "1":
            student_enrollment_menu()
        elif choice == "0":
            return "exit"
        else:
            print("เลือกเมนูไม่ถูกต้อง\n")


def instructor_portal():
    """เมนูสำหรับอาจารย์ตามโครงสร้างใน titit.txt"""
    while True:
        print("\n==========================================")
        print(" ระบบลงทะเบียนเรียน (For Instructor)")
        print("==========================================")
        print("1) จัดการรายวิชา (Courses)")
        print("2) จัดการนักศึกษา (Students)")
        print("3) การลงทะเบียนเรียน (Enrollments)")
        print("4) อาจารย์ผู้สอน (Instructor)")
        print("5) สร้างรายงานสรุป (Generate Report)")
        print("0) ออกจากโปรแกรม (Exit)")
        choice = input("เลือกเมนู (0-5): ").strip()
        if choice == "1":
            course_menu()
        elif choice == "2":
            student_menu()
        elif choice == "3":
            enrollment_menu()
        elif choice == "4":
            instructor_menu()
        elif choice == "5":
            report_menu()
        elif choice == "0":
            return "exit"
        else:
            print("เลือกเมนูไม่ถูกต้อง\n")


def main_menu():
    """เมนูหลักแยก Student / Instructor ตาม titit.txt"""
    while True:
        print("==========================================")
        print(" ระบบลงทะเบียนเรียน (CLI) ")
        print("==========================================")
        print("1) นักศึกษา (For Students)")
        print("2) อาจารย์ผู้สอน (For Instructor)")
        print("0) ออกจากโปรแกรม (Exit)")
        choice = input("เลือกเมนู (0-2): ").strip()
        if choice == "1":
            if student_portal() == "exit":
                choice = "0"
            else:
                continue
        elif choice == "2":
            if instructor_portal() == "exit":
                choice = "0"
            else:
                continue
        elif choice == "0":
            # สร้าง Report 1-3 อัตโนมัติก่อนปิดโปรแกรม
            try:
                generate_all_reports()
            except Exception as exc:
                print(f"ไม่สามารถสร้างรายงานอัตโนมัติได้: {exc}")

            for fname in [STUDENT_FILE, COURSE_FILE, ENROLL_FILE]:
                if os.path.exists(fname):
                    try:
                        fd = os.open(fname, os.O_RDWR)
                        os.fsync(fd)
                        os.close(fd)
                    except OSError:
                        pass
            log_action("ปิดโปรแกรม (Exit)")
            print("บันทึกและซิงค์ข้อมูลเรียบร้อย ปิดโปรแกรมเรียบร้อยแล้ว")
            break
        else:
            print("เลือกเมนูไม่ถูกต้อง ลองใหม่อีกครั้ง\n")


if __name__ == "__main__":
    seed_default_courses()
    seed_default_students()
    main_menu()