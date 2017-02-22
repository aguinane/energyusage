from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FileField, SelectField
from wtforms.validators import DataRequired, length


class UsernamePasswordForm(FlaskForm):
    """ Login and signup form """
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class FileForm(FlaskForm):
    """ Upload form to specify csv file """
    upload_file = FileField('Data File', validators=[DataRequired()])
    file_type = SelectField(u'File Type',
                            choices=[('nem', 'NEM12/NEM13'), ('interval', 'Interval Data')])
    uom = SelectField(u'Unit of Measure (for interval data only)',
                      choices=[('kWh', 'kWh'), ('Wh', 'Wh'), ('Wm', 'Wm')])


class NewMeter(FlaskForm):
    """ Form for creating new meter """
    meter_name = StringField(
        'Meter Name / NMI', validators=[DataRequired(), length(min=3, max=20)])
    sharing = SelectField(u'Sharing Type',
                          choices=[('public', 'Public'), ('private', 'Private')])
