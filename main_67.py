import struct
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
MAX_CREDITS_PER_STUDENT = 22


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
#  1) นักศึกษา (Student)
# ============================================================

def add_student():
    print("\n--- เพิ่มนักศึกษาใหม่ ---")
    student_id = ask_int("ป้อน Student ID / ปีการศึกษา (เช่น 68, 69): ")
    code = ask_student_code("ป้อนรหัสนักศึกษา (ตัวเลข 13 หลัก เช่น 6906022610067): ")
    name = input("ป้อนชื่อ-สกุล: ")
    major = input("ป้อนสาขาวิชา: ")
    year = ask_int("ป้อนชั้นปี: ")

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
                new_name = input("ชื่อใหม่ (Enter = ไม่เปลี่ยน): ") or curr_name
                new_year = ask_int("ชั้นปีใหม่ (Enter = ไม่เปลี่ยน): ", allow_empty=True, default=u[4])

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
    code = input("ป้อนรหัสวิชา (เช่น CS101): ")
    title = input("ป้อนชื่อรายวิชา: ")
    category = input("ป้อนหมวดวิชา (เช่น Core, Elective, GenEd): ")
    credits = ask_int("ป้อนจำนวนหน่วยกิต: ")
    fee = ask_float("ป้อนค่าธรรมเนียมวิชา (บาท): ")
    instructor = input("ป้อนชื่ออาจารย์ผู้สอน (เว้นว่างได้ ถ้ายังไม่กำหนด): ").strip()

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


def change_enrollment():
    """เปลี่ยนวิชาที่ลงทะเบียน (Update Enrollment) -- แก้ course_id ของรายการลงทะเบียนเดิม"""
    print("\n--- เปลี่ยนวิชาที่ลงทะเบียน ---")
    if not os.path.exists(ENROLL_FILE) or os.path.getsize(ENROLL_FILE) == 0:
        print("ยังไม่มีข้อมูลการลงทะเบียนในระบบ\n")
        return

    search_id = ask_int("ป้อน Enrollment ID ที่ต้องการเปลี่ยนวิชา: ")

    with open(ENROLL_FILE, "r+b") as f:
        index = 0
        found = False
        while True:
            offset = index * ENROLL_SIZE
            f.seek(offset)
            data = f.read(ENROLL_SIZE)
            if not data:
                break
            u = struct.unpack(ENROLL_FORMAT, data)
            if u[0] == search_id and u[4] == 1:
                found = True
                student_code = decode_str(u[1])
                old_course_id = u[2]
                old_course_title = None
                for c in read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE):
                    if c[0] == old_course_id:
                        old_course_title = decode_str(c[2])
                        break
                print(f"พบรายการเดิม: นักศึกษา {student_code} ลงวิชา ID {old_course_id}"
                      + (f" ({old_course_title})" if old_course_title else ""))

                new_course_id = ask_int("ป้อน Course ID ใหม่ที่ต้องการเปลี่ยนไปลง: ")

                if new_course_id == old_course_id:
                    print("วิชาใหม่เหมือนวิชาเดิม ไม่มีอะไรเปลี่ยนแปลง\n")
                    return

                new_course_rec = None
                for c in read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE):
                    if c[0] == new_course_id and c[6] == 1:
                        new_course_rec = c
                        break
                if new_course_rec is None:
                    print("ไม่พบรายวิชาใหม่นี้ในระบบ (หรือถูกลบไปแล้ว)\n")
                    return
                if new_course_rec[7] == 1:
                    print("วิชาใหม่นี้เต็ม/ปิดรับลงทะเบียนแล้ว\n")
                    return

                # กันลงทะเบียนซ้ำวิชาเดียวกันที่มีอยู่แล้ว
                for r in read_all_records(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE):
                    if decode_str(r[1]) == student_code and r[2] == new_course_id and r[4] == 1:
                        print("นักศึกษาคนนี้ลงทะเบียนวิชาใหม่นี้อยู่แล้ว\n")
                        return

                # ตรวจสอบหน่วยกิตรวม (ไม่นับวิชาเดิมที่กำลังจะถูกแทนที่)
                other_credits = get_total_credits(student_code, exclude_enroll_id=search_id)
                new_total = other_credits + new_course_rec[4]
                if new_total > MAX_CREDITS_PER_STUDENT:
                    print(f"เปลี่ยนวิชาไม่ได้! หน่วยกิตรวมจะเกินเพดานที่กำหนด")
                    print(f"  วิชาอื่นที่ลงอยู่ : {other_credits} หน่วยกิต")
                    print(f"  วิชาใหม่          : {new_course_rec[4]} หน่วยกิต")
                    print(f"  รวมจะเป็น         : {new_total} หน่วยกิต (เพดาน {MAX_CREDITS_PER_STUDENT} หน่วยกิต)\n")
                    return

                date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                date_bytes = encode_fixed(date_str, 20)
                packed_new = struct.pack(ENROLL_FORMAT, u[0], u[1], new_course_id, date_bytes, 1)
                f.seek(offset)
                f.write(packed_new)
                log_action(f"เปลี่ยนวิชาลงทะเบียน EnrollID={search_id} StudentCode={student_code} "
                           f"Course {old_course_id} -> {new_course_id}")
                print(f"เปลี่ยนวิชาเรียบร้อยแล้ว! (Enrollment ID: {search_id})\n")
                break
            index += 1
        if not found:
            print("ไม่พบรายการลงทะเบียนนี้ หรือถูกยกเลิกไปแล้ว\n")


def cancel_enrollment():
    print("\n--- ยกเลิกการลงทะเบียน (Soft Delete) ---")
    if not os.path.exists(ENROLL_FILE) or os.path.getsize(ENROLL_FILE) == 0:
        print("ยังไม่มีข้อมูลการลงทะเบียนในระบบ\n")
        return
    search_id = ask_int("ป้อน Enrollment ID ที่ต้องการยกเลิก: ")

    with open(ENROLL_FILE, "r+b") as f:
        index = 0
        found = False
        while True:
            offset = index * ENROLL_SIZE
            f.seek(offset)
            data = f.read(ENROLL_SIZE)
            if not data:
                break
            u = struct.unpack(ENROLL_FORMAT, data)
            if u[0] == search_id and u[4] == 1:
                found = True
                packed_del = struct.pack(ENROLL_FORMAT, u[0], u[1], u[2], u[3], 0)
                f.seek(offset)
                f.write(packed_del)
                log_action(f"ยกเลิกการลงทะเบียน EnrollID={search_id}")
                print("ยกเลิกการลงทะเบียนเรียบร้อยแล้ว!\n")
                break
            index += 1
        if not found:
            print("ไม่พบรายการลงทะเบียนนี้\n")


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
#  4) สร้างรายงานสรุป (report.txt)
# ============================================================

def generate_report():
    print("\n--- กำลังสร้างไฟล์รายงาน report.txt ---")

    students = read_all_records(STUDENT_FILE, STUDENT_FORMAT, STUDENT_SIZE)
    courses = read_all_records(COURSE_FILE, COURSE_FORMAT, COURSE_SIZE)
    enrolls = read_all_records(ENROLL_FILE, ENROLL_FORMAT, ENROLL_SIZE)

    active_students = [s for s in students if s[5] == 1]
    active_courses = [c for c in courses if c[6] == 1]
    active_enrolls = [e for e in enrolls if e[4] == 1]

    fees = [c[5] for c in active_courses] or [0.0]
    min_fee, max_fee = min(fees), max(fees)
    avg_fee = sum(fees) / len(fees)

    cat_counts = {}
    for c in active_courses:
        cat = decode_str(c[3])
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    free_students = len(students) - len(active_students)
    free_courses = len(courses) - len(active_courses)
    free_enrolls = len(enrolls) - len(active_enrolls)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    recent_logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            recent_logs = f.readlines()[-10:]

    with open("report.txt", "w", encoding="utf-8") as f:
        f.write("Course Registration System - Summary Report\n")
        f.write(f"Generated At : {now}\n")
        f.write("App Version  : 2.1 (Multi-Student ID Supported)\n")
        f.write("Endianness   : Little-Endian\n")
        f.write("Encoding     : UTF-8 (fixed-length)\n")
        f.write(f"Files        : {STUDENT_FILE}, {COURSE_FILE}, {ENROLL_FILE}\n\n")

        f.write("=== รายวิชา (Courses) ===\n")
        sep = "-" * 120 + "\n"
        f.write(sep)
        f.write(f"| {'ID':<6} | {'Code':<10} | {'Title':<20} | {'Category':<12} | {'Credits':<7} | {'Fee':<9} | {'Status':<7} | {'Full':<5} | {'Instructor':<22} |\n")
        f.write(sep)
        for c in courses:
            st = "Active" if c[6] == 1 else "Deleted"
            full = "Yes" if c[7] == 1 else "No"
            instructor = decode_str(c[8]) or "-"
            f.write(f"| {c[0]:<6} | {decode_str(c[1])[:10]:<10} | {decode_str(c[2])[:20]:<20} | "
                     f"{decode_str(c[3])[:12]:<12} | {c[4]:<7} | {c[5]:<9.2f} | {st:<7} | {full:<5} | {instructor[:22]:<22} |\n")
        f.write(sep + "\n")

        f.write("=== นักศึกษา (Students) ===\n")
        sep2 = "-" * 75 + "\n"
        f.write(sep2)
        f.write(f"| {'YearID':<6} | {'Code':<15} | {'Name':<25} | {'Major':<15} | {'Status':<7} |\n")
        f.write(sep2)
        for s in students:
            st = "Active" if s[5] == 1 else "Deleted"
            f.write(f"| {s[0]:<6} | {decode_str(s[1])[:15]:<15} | {decode_str(s[2])[:25]:<25} | "
                     f"{decode_str(s[3])[:15]:<15} | {st:<7} |\n")
        f.write(sep2 + "\n")

        f.write("=== การลงทะเบียน (Enrollments) ===\n")
        sep3 = "-" * 75 + "\n"
        f.write(sep3)
        f.write(f"| {'EnrollID':<9} | {'StudentCode':<15} | {'CourseID':<9} | {'Date':<20} | {'Status':<9} |\n")
        f.write(sep3)
        for e in enrolls:
            st = "Active" if e[4] == 1 else "Cancelled"
            f.write(f"| {e[0]:<9} | {decode_str(e[1]):<15} | {e[2]:<9} | {decode_str(e[3]):<20} | {st:<9} |\n")
        f.write(sep3 + "\n")

        f.write("Summary\n")
        f.write(f"- Courses  : Total={len(courses)}, Active={len(active_courses)}, Deleted={free_courses}\n")
        f.write(f"- Students : Total={len(students)}, Active={len(active_students)}, Deleted={free_students}\n")
        f.write(f"- Enrolls  : Total={len(enrolls)}, Active={len(active_enrolls)}, Cancelled={free_enrolls}\n\n")

        f.write("Fee Statistics (THB, Active courses only)\n")
        f.write(f"- Min : {min_fee:.2f}\n")
        f.write(f"- Max : {max_fee:.2f}\n")
        f.write(f"- Avg : {avg_fee:.2f}\n\n")

        f.write("Courses by Category (Active only)\n")
        for cat_name, count in cat_counts.items():
            f.write(f"- {cat_name} : {count}\n")
        f.write("\n")

        f.write("ประวัติการทำงานล่าสุด (Recent Operation History)\n")
        if recent_logs:
            for line in recent_logs:
                f.write(f"- {line.strip()}\n")
        else:
            f.write("- ไม่มีประวัติการทำงาน\n")

    log_action("สร้างรายงาน report.txt")
    print("สร้างไฟล์ report.txt เรียบร้อยแล้ว!\n")


# ============================================================
#  วิชาตั้งต้น (Preset Courses)
# ============================================================

DEFAULT_COURSES = [
    (1001, "CS101", "Computer Programming", "Core", 3, 1500.0),
    (1002, "GE101", "English Communication", "GenEd", 3, 800.0),
    (2001, "SP101", "Table Tennis", "Sport", 1, 0.0),
]


def seed_default_courses():
    if os.path.exists(COURSE_FILE) and os.path.getsize(COURSE_FILE) > 0:
        return 

    with open(COURSE_FILE, "ab") as f:
        for course_id, code, title, category, credits, fee in DEFAULT_COURSES:
            code_b = encode_fixed(code, 15)
            title_b = encode_fixed(title, 50)
            cat_b = encode_fixed(category, 20)
            instructor_b = encode_fixed("", 60)
            packed = struct.pack(COURSE_FORMAT, course_id, code_b, title_b, cat_b, credits, fee, 1, 0, instructor_b)
            f.write(packed)
    log_action("สร้างวิชาตั้งต้น (Preset Courses) อัตโนมัติตอนรันครั้งแรก")


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
    while True:
        print("\n---- การลงทะเบียนเรียน (Enrollments) ----")
        print("1) ลงทะเบียน")
        print("2) เปลี่ยนวิชาที่ลงทะเบียน")
        print("3) ยกเลิกการลงทะเบียน")
        print("4) ดูข้อมูลการลงทะเบียน")
        print("5) ดูวิชาที่เปิดให้ลงทะเบียน")
        print("6) เพิ่มวิชาสำหรับลงทะเบียน")
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
        elif c == "6":
            add_course()
        elif c == "0":
            break
        else:
            print("เลือกเมนูไม่ถูกต้อง\n")


def main_menu():
    while True:
        print("==========================================")
        print(" ระบบลงทะเบียนเรียน (CLI) ")
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
            generate_report()
        elif choice == "0":
            for fname in [STUDENT_FILE, COURSE_FILE, ENROLL_FILE]:
                if os.path.exists(fname):
                    try:
                        fd = os.open(fname, os.O_RDWR)
                        os.fsync(fd)
                        os.close(fd)
                    except OSError:
                        pass
            
            generate_report()
            log_action("ปิดโปรแกรม (Exit)")
            print("บันทึกและซิงค์ข้อมูลเรียบร้อย ปิดโปรแกรมเรียบร้อยแล้ว")
            break
        else:
            print("เลือกเมนูไม่ถูกต้อง ลองใหม่อีกครั้ง\n")


if __name__ == "__main__":
    seed_default_courses()
    main_menu()