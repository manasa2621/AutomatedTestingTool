from flask import render_template, url_for, jsonify, request, redirect,session, flash
from aatserver import app, db
from sqlalchemy import text
import json

@app.route("/check_db_connection")
def check_db_connection():
    try:
        query = text('SELECT * FROM comment')
        cursor = db.session.execute(query)
        assessments = cursor.fetchall()
        return jsonify({"status": "success", "message": "Database connection successful"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/fetch_assessments')
def fetch_assessments():
    try:
        query = text('SELECT * FROM assessment')
        assessments = db.session.execute(query).fetchall()
        
        assessments_data = []
        for assessment in assessments:
            assessments_data.append({
                'id': assessment.id,
                'name': assessment.name,
                'difficulty_level': assessment.difficulty_level,
                'total_questions': assessment.total_questions,
                'total_marks': assessment.total_marks
            })
        
        return jsonify({"status": "success", "assessments": assessments_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
        
@app.route('/formative_assessment')
def render_formative_assessment():
    return render_template('formative_assessment.html')

@app.route('/view_assessment/<int:assessment_id>')
def view_assessment(assessment_id):
    try:
        return render_template('view_assessment_staff.html', assessment_id=assessment_id)
    except Exception as e:
        flash("An error occurred: " + str(e))
        return redirect(url_for('render_formative_assessment'))

@app.route('/fetch_assessment_data/<int:assessment_id>')
def fetch_assessment_data(assessment_id):
    try:
        query = """
            SELECT 
                a.id AS assessment_id,
                a.name AS assessment_name,
                a.difficulty_level,
                a.total_questions,
                a.total_marks,
                q.id AS question_id,
                q.question_text,
                q.marks AS question_marks,
                q.question_type,
                c.id AS comment_id,
                c.content AS comment_content,
                o.id AS option_id,
                o.option_text,
                o.is_correct
            FROM 
                assessment a
            JOIN 
                question q ON a.id = q.assessment_id
            LEFT JOIN 
                comment c ON q.id = c.question_id
            LEFT JOIN 
                option o ON q.id = o.question_id
            WHERE 
                a.id = :id
            """
        result = db.session.execute(text(query), {"id": assessment_id}).fetchall()

        assessment_data = {}
        for row in result:
            assessment_id = row[0]
            if assessment_id not in assessment_data:
                assessment_data[assessment_id] = {
                    "assessment_id": row[0],
                    "assessment_name": row[1],
                    "difficulty_level": row[2],
                    "total_questions": row[3],
                    "total_marks": row[4],
                    "questions": {}
                }
            question_id = row[5]
            if question_id not in assessment_data[assessment_id]['questions']:
                assessment_data[assessment_id]['questions'][question_id] = {
                    "question_id": row[5],
                    "question_text": row[6],
                    "question_marks": row[7],
                    "question_type": row[8],
                    "comments": [],
                    "options": []
                }
            if row[9]:
                assessment_data[assessment_id]['questions'][question_id]['comments'].append({
                    "comment_id": row[9],
                    "comment_content": row[10]
                })
            if row[11]:
                assessment_data[assessment_id]['questions'][question_id]['options'].append({
                    "option_id": row[11],
                    "option_text": row[12],
                    "is_correct": row[13]
                })

        return jsonify({"status": "success", "assessment_data": json.dumps(assessment_data)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/add_assessment')
def render_add_assessments():
    return render_template('add_assessments.html')

@app.route('/view-results')
def view_results():
    marks = request.args.get('marks')
    assessment_id=request.args.get('assessment_id')
    return render_template('view-results.html', marks=marks,assessment_id=assessment_id)

@app.route('/submit-assessment', methods=['POST'])
def submit_assessment():
    try:
        assessment_data = request.json

        db.session.execute(text("""
            INSERT INTO assessment (name, difficulty_level, total_questions, total_marks)
            VALUES (:name, :difficulty, :total_questions, :total_marks)
        """), {
            'name': assessment_data['name'],
            'difficulty': assessment_data['difficulty'],
            'total_questions': assessment_data['total_questions'],
            'total_marks': assessment_data['total_marks']
        })

        db.session.commit()

        result = db.session.execute(text("SELECT last_insert_rowid()"))
        assessment_id = result.fetchone()[0]
    
        for i in range(int(assessment_data['total_questions'])):
            db.session.execute(text("""
                INSERT INTO question (assessment_id, question_text, marks, question_type)
                VALUES (:assessment_id, :question_text, :marks, :question_type)
            """), {
                'assessment_id': assessment_id,
                'question_text': assessment_data['questions[]'][i],
                'marks': assessment_data['marks[]'][i],
                'question_type': assessment_data['question_types[]'][i]
            })

            result = db.session.execute(text("SELECT last_insert_rowid()"))
            question_id = result.fetchone()[0]

            if assessment_data['question_types[]'][i] == 'mcq':
                for j, option_text in enumerate(assessment_data['options[]'][4*i:4*(i+1)]):
                    db.session.execute(text("""
                        INSERT INTO option (question_id, option_text, is_correct)
                        VALUES (:question_id, :option_text, :is_correct)
                    """), {
                        'question_id': question_id,
                        'option_text': option_text,
                        'is_correct': 1 if str(j) == assessment_data['correct_answers[]'][i] else 0
                    })
            else: 
                db.session.execute(text("""
                    INSERT INTO option (question_id, option_text, is_correct)
                    VALUES (:question_id, :option_text, :is_correct)
                """), {
                    'question_id': question_id,
                    'option_text': 'True',
                    'is_correct': 1 if assessment_data['correct_answers_true_false[]'][i] == 'true' else 0
                })
                db.session.execute(text("""
                    INSERT INTO option (question_id, option_text, is_correct)
                    VALUES (:question_id, :option_text, :is_correct)
                """), {
                    'question_id': question_id,
                    'option_text': 'False',
                    'is_correct': 1 if assessment_data['correct_answers_true_false[]'][i] == 'false' else 0
                })

            if assessment_data['comments[]'][i]:
                db.session.execute(text("""
                    INSERT INTO comment (question_id, content)
                    VALUES (:question_id, :content)
                """), {
                    'question_id': question_id,
                    'content': assessment_data['comments[]'][i]
                })

        db.session.commit()

        return jsonify({'message': 'Assessment submitted successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete-assessment/<int:assessment_id>', methods=['DELETE'])
def delete_assessment(assessment_id):
    try:
        db.session.execute(
            text("DELETE FROM comment WHERE question_id IN (SELECT id FROM question WHERE assessment_id = :id)"),
            {"id": assessment_id}
        )

        db.session.execute(
            text("DELETE FROM option WHERE question_id IN (SELECT id FROM question WHERE assessment_id = :id)"),
            {"id": assessment_id}
        )

        db.session.execute(
            text("DELETE FROM question WHERE assessment_id = :id"),
            {"id": assessment_id}
        )

        db.session.execute(
            text("DELETE FROM assessment WHERE id = :id"),
            {"id": assessment_id}
        )

        db.session.commit()

        return jsonify({"status": "success", "message": f"Assessment {assessment_id} and associated data deleted successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    
@app.route('/take_assessment/<int:assessment_id>')
def take_assessment(assessment_id):
    try:
        return render_template('take-assessment.html', assessment_id=assessment_id)
    except Exception as e:
        flash("An error occurred: " + str(e))
        return redirect(url_for('view_assessments'))

@app.route('/view_assessments')
def view_assessments():
    return render_template('view-assessments.html')

@app.route('/edit_assessment/<int:assessment_id>')
def edit_assessment(assessment_id):
    try:
        return render_template('update-assessments.html', assessment_id=assessment_id)
    except Exception as e:
        flash("An error occurred: " + str(e))
        return redirect(url_for('formative_assessment'))

@app.route('/update-assessment/<int:assessment_id>', methods=['PUT'])
def update_assessment(assessment_id):
    try:
        updated_data = request.json

        db.session.execute(
            text("""
            UPDATE assessment 
            SET 
                name = :name, 
                difficulty_level = :difficulty,
                total_questions = :total_questions,
                total_marks = :total_marks 
            WHERE id = :id
            """),
            {
                'name': updated_data['edit_assessment_name'],
                'difficulty': updated_data['edit_difficulty_level'],
                'total_questions': updated_data['edit_total_questions'],
                'total_marks': updated_data['edit_total_marks'],
                'id': assessment_id
            }
        )

        for question_data in updated_data['questions']:
            db.session.execute(
                text("""
                UPDATE question 
                SET question_text = :question_text, 
                    marks = :marks,
                    question_type = :question_type 
                WHERE id = :id
                """),
                {
                    'question_text': question_data['question_text'],
                    'marks': question_data['question_marks'],
                    'question_type': question_data['question_type'],
                    'id': question_data['question_id']
                }
            )

            for comment_data in question_data['comments']:
                db.session.execute(
                    text("""
                    UPDATE comment 
                    SET content = :content 
                    WHERE id = :id
                    """),
                    {
                        'content': comment_data['comment_content'],
                        'id': comment_data['comment_id']
                    }
                )

        db.session.commit()

        return jsonify({"status": "success", "message": "Assessment details updated successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/feedback', methods=['POST'])
def handle_feedback():
    if request.method == 'POST':
        data = request.json

        feedback = data.get('feedback')
        student_name = data.get('student_name')
        assessment_id = data.get('assessment_id')

        if feedback and student_name and assessment_id:
            try:
                db.session.execute(text("""
                    INSERT INTO feedback (feedback, student_name, assessment_id)
                    VALUES (:feedback, :student_name, :assessment_id)
                """), {
                    'feedback': feedback,
                    'student_name': student_name,
                    'assessment_id': assessment_id
                })
                db.session.commit()
                return jsonify({'message': 'Feedback submitted successfully'}), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        else:
            return jsonify({'error': 'Missing data in the request'}), 400

@app.route('/view-feedback', methods=['GET'])
def get_feedback():
    try:
        feedback_data = db.session.execute(text("""
            SELECT f.feedback, f.student_name, a.name
            FROM feedback f
            INNER JOIN assessment a ON f.assessment_id = a.id
        """)).fetchall()

        feedback_list = [{'feedback': feedback, 'student_name': student_name, 'assessment_name': assessment_name} 
                         for feedback, student_name, assessment_name in feedback_data]

        return jsonify({'feedback_list': feedback_list}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/viewstudent-feedback')
def view_feedback():
    return render_template('view-feedback.html')

@app.route('/view_staff_comments/<int:assessment_id>')
def view_staff_comments(assessment_id):
    try:
        return render_template('view_staff_comments.html', assessment_id=assessment_id)
    except Exception as e:
        flash("An error occurred: " + str(e))
        return redirect(url_for('view_assessments'))

@app.route('/view_student_comments/<int:assessment_id>')
def view_student_comment(assessment_id):
    try:
        return render_template('view_student_comments.html', assessment_id=assessment_id)
    except Exception as e:
        flash("An error occurred: " + str(e))
        return redirect(url_for('view_assessments'))

@app.route('/view_student_comment/<int:assessment_id>', methods=['GET'])
def view_student_comments(assessment_id):
    student_name = request.args.get('student_name')

    if not student_name:
        return jsonify({'error': 'Missing student_name parameter'}), 400

    try:
        result = db.session.execute(text("""
            SELECT feedback
            FROM feedback
            WHERE assessment_id = :assessment_id AND student_name = :student_name
        """), {
            'assessment_id': assessment_id,
            'student_name': student_name
        })

        feedback_row = result.fetchone()

        if feedback_row:
            feedback = feedback_row[0]
            return jsonify({'feedback': feedback}), 200
        else:
            return jsonify({'message': 'You have not given feedback for this assessment'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update_feedback/<int:assessment_id>', methods=['POST'])
def update_feedback(assessment_id):
    student_name = request.json.get('student_name')
    new_feedback = request.json.get('new_feedback')

    if not student_name or not new_feedback:
        return jsonify({'error': 'Missing student_name or new_feedback parameter'}), 400

    try:
        update_query = text("""
            UPDATE feedback
            SET feedback = :new_feedback
            WHERE assessment_id = :assessment_id AND student_name = :student_name
        """)

        result = db.session.execute(
            update_query,
            {
                'new_feedback': new_feedback,
                'assessment_id': assessment_id,
                'student_name': student_name
            }
        )

        db.session.commit()

        if result.rowcount > 0:
            return jsonify({'message': 'Feedback updated successfully'}), 200
        else:
            return jsonify({'message': 'Feedback not found for this assessment and student'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_comment', methods=['DELETE'])
def delete_comment():
    student_name = request.args.get('student_name')
    feedback = request.args.get('feedback')

    if not student_name or not feedback:
        return jsonify({'error': 'Missing student_name or feedback parameter'}), 400

    try:
        delete_query = text("""
            DELETE FROM feedback
            WHERE student_name = :student_name 
            AND feedback = :feedback
        """)
        result = db.session.execute(delete_query, {
            'student_name': student_name,
            'feedback': feedback
        })

        db.session.commit() 

        if result.rowcount > 0:
            return jsonify({'message': 'Feedback deleted successfully'}), 200
        else:
            return jsonify({'message': 'Feedback not found for deletion'}), 404

    except Exception as e:
        db.session.rollback()  
        return jsonify({'error': str(e)}), 500