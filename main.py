import time
from fastapi import FastAPI, HTTPException, status, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import User, Student, Subject, StudentSubject, hash_password, verify_password
from schemas import (
    UserRegister, UserLogin, UserResponse, UserUpdateProfile,
    StudentCreate, SubjectCreate
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Student & Subject Management")

def send_welcome_email(email: str):
    print(f'Sending welcome email to "{email}"')
    time.sleep(3)  # 3 წამიანი დაყოვნება იმიტაციისთვის
    print(f'Email sent to "{email}"')


@app.get("/")
def read_root():
    return {"message": "პროექტი წარმატებით გაეშვა!"}


@app.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(
    user: UserRegister, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        (User.username == user.username) | (User.email == user.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=400, 
            detail="მომხმარებელი ამ მომხმარებლის სახელით ან ელ-ფოსტით უკვე არსებობს"
        )
    
    hashed_pwd = hash_password(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_pwd,
        is_admin=user.is_admin
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    background_tasks.add_task(send_welcome_email, new_user.email)

    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "is_admin": new_user.is_admin,
        "message": "მომხმარებელი წარმატებით დარეგისტრირდა"
    }


@app.post("/login")
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="არასწორი მომხმარებლის სახელი ან პაროლი"
        )
    
    return {
        "message": "ავტორიზაცია წარმატებით გაიარეთ!", 
        "username": db_user.username,
        "is_admin": db_user.is_admin
    }


@app.put("/users/me", response_model=UserResponse)
def update_own_profile(user_id: int, profile_data: UserUpdateProfile, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="მომხმარებელი ვერ მოიძებნა")

    if profile_data.username:
        user.username = profile_data.username
    if profile_data.email:
        user.email = profile_data.email
    if profile_data.password:
        user.hashed_password = hash_password(profile_data.password)

    db.commit()
    db.refresh(user)
    return user


@app.get("/users", response_model=list[UserResponse])
def get_all_users(admin_id: int, db: Session = Depends(get_db)):
    admin_user = db.query(User).filter(User.id == admin_id).first()
    if not admin_user or not admin_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="წვდომა უარყოფილია: ეს მოქმედება ხელმისაწვდომია მხოლოდ ადმინისთვის"
        )
    return db.query(User).all()


@app.get("/users/{user_id}", response_model=UserResponse)
def get_user_by_id(user_id: int, admin_id: int, db: Session = Depends(get_db)):
    admin_user = db.query(User).filter(User.id == admin_id).first()
    if not admin_user or not admin_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="წვდომა უარყოფილია: ეს მოქმედება ხელმისაწვდომია მხოლოდ ადმინისთვის"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="მომხმარებელი ვერ მოიძებნა")

    return user


@app.delete("/users/{user_id}")
def delete_user(user_id: int, admin_id: int, db: Session = Depends(get_db)):
    admin_user = db.query(User).filter(User.id == admin_id).first()
    if not admin_user or not admin_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="წვდომა უარყოფილია: ეს მოქმედება ხელმისაწვდომია მხოლოდ ადმინისთვის"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="მომხმარებელი ვერ მოიძებნა")

    db.delete(user)
    db.commit()
    return {"message": f"მომხმარებელი ID: {user_id} წარმატებით წაიშალა"}


# სტუდენტები
@app.post("/students")
def create_student(student: StudentCreate, db: Session = Depends(get_db)):
    new_student = Student(
        first_name=student.first_name,
        last_name=student.last_name,
        email=student.email
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return new_student

@app.get("/students")
def get_students(db: Session = Depends(get_db)):
    return db.query(Student).all()

@app.get("/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@app.delete("/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(student)
    db.commit()
    return {"message": "Student deleted"}


# საგნები
@app.post("/subjects")
def create_subject(subject: SubjectCreate, db: Session = Depends(get_db)):
    new_subject = Subject(
        title=subject.title,
        duration=subject.duration
    )
    db.add(new_subject)
    db.commit()
    db.refresh(new_subject)
    return new_subject

@app.get("/subjects")
def get_subjects(db: Session = Depends(get_db)):
    return db.query(Subject).all()

@app.get("/subjects/{subject_id}")
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject

@app.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    db.delete(subject)
    db.commit()
    return {"message": "Subject deleted"}


@app.post("/students/{student_id}/subjects/{subject_id}")
def add_subject_to_student(student_id: int, subject_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    subject = db.query(Subject).filter(Subject.id == subject_id).first()

    if not student or not subject:
        raise HTTPException(status_code=404, detail="Student or Subject not found")

    student_subject = StudentSubject(
        student_id=student_id,
        subject_id=subject_id
    )

    db.add(student_subject)
    db.commit()
    db.refresh(student_subject)
    return student_subject

@app.get("/students/{student_id}/subjects")
def get_student_subjects(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student.subjects

@app.get("/subjects/{subject_id}/students")
def get_subject_students(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject.students

@app.delete("/students/{student_id}/subjects/{subject_id}")
def remove_subject_from_student(student_id: int, subject_id: int, db: Session = Depends(get_db)):
    student_subject = db.query(StudentSubject).filter(
        StudentSubject.student_id == student_id,
        StudentSubject.subject_id == subject_id
    ).first()

    if not student_subject:
        raise HTTPException(status_code=404, detail="Student is not enrolled in this subject")

    db.delete(student_subject)
    db.commit()
    return {"message": "Subject removed from student"}

