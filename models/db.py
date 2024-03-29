from datetime import datetime
## app configuration made easy. Look inside private/appconfig.ini
from gluon.contrib.appconfig import AppConfig
## once in production, remove reload=True to gain full speed
myconf = AppConfig(reload=True)

## by default give a view/generic.extension to all actions from localhost
## none otherwise. a pattern can be 'controller/function.extension'
response.generic_patterns = ['*'] if request.is_local else []
## choose a style for forms
response.formstyle = myconf.take('forms.formstyle')  # or 'bootstrap3_stacked' or 'bootstrap2' or other
response.form_label_separator = myconf.take('forms.separator')

from gluon.tools import Auth, Service, PluginManager


db = DAL('sqlite://storage.db')
auth = Auth(db, controller='auth')
service = Service()
plugins = PluginManager()

## create all tables needed by auth if not custom tables
auth.define_tables(username=True, signature=False)
db.auth_user.username.requires = IS_NOT_IN_DB(db, 'auth_user.username')

## configure email
mail = auth.settings.mailer
mail.settings.server = 'logging' if request.is_local else myconf.take('smtp.server')
mail.settings.sender = myconf.take('smtp.sender')
mail.settings.login = myconf.take('smtp.login')

## configure auth policy
auth.settings.registration_requires_verification = False
auth.settings.registration_requires_approval = False
auth.settings.reset_password_requires_verification = True

# configure auth messages
auth.messages.logged_in = None
auth.messages.logged_out = None

# allow json reqests
response.generic_patterns = ['*.json']

#########################################################################
## Define your tables below (or better in another model file) for example
##
## >>> db.define_table('mytable',Field('myfield','string'))
##
## Fields can be 'string','text','password','integer','double','boolean'
##       'date','time','datetime','blob','upload', 'reference TABLENAME'
## There is an implicit 'id integer autoincrement' field
## Consult manual for more options, validators, etc.
##
## More API examples for controllers:
##
## >>> db.mytable.insert(myfield='value')
## >>> rows=db(db.mytable.myfield=='value').select(db.mytable.ALL)
## >>> for row in rows: print row.id, row.myfield
#########################################################################

## after defining tables, uncomment below to enable auditing
# auth.enable_record_versioning(db)

#User settings table
#+user refers to a user
#+trade_non_tradable_items whether the user is happy to receive
#        requests for items which they have not marked as tradable
db.define_table('user_settings',
        Field('user', db.auth_user, default=auth.user_id,
              notnull=True, unique=True, ondelete="CASCADE"),
        Field('trade_non_tradable_items', type='boolean', default=True,
              notnull=True)
)

#Collection table
#+owner refers to User
#+name  should be unique per owner, but not be unique in the DB (e.g Default)
#+public
db.define_table('collection',
        Field('owner', db.auth_user, default=auth.user_id,
              notnull=True, ondelete="CASCADE"),
        Field('name', type='string', length=64, required=True,
              notnull=True),
        Field('public', type="boolean", default=False,
              notnull=True)
)

#Category table
#+name  used as enumeration values by Object.category
db.define_table('category',
        Field('name', type='string', length=32,
              notnull=True, unique=True)
)

#Object table
#+owner refers to User
#+collection refers to Collection. Allow null, for loose Objects
#+name
#+price non-negative value in GBP; assumed "0.0" => "not set"
#+category refers to Category
#+quantity quantity (owned) subset; non-negative integer
#+tradable_quantity quantity (tradable) subset; non-negative integer
#+wanted_quantity quantity (wanted) subset; non-negative integer
#+description
#+image image is required, but may be the default thumbnail

db.define_table('object',
        Field('owner', db.auth_user, default=auth.user_id,
              notnull=True, ondelete="CASCADE",
              comment = T("The owner of the item.")),
        Field('collection',  db.collection, required=True,
              notnull=False, ondelete="SET NULL",
              label ='Collection',
              requires = IS_IN_DB(db(db.collection.owner == auth.user_id), db.collection.id, '%(name)s',
                                  error_message = "This field cannot be empty. Please select the collection that you want to add this item to."),
              comment = T("Choose one of your collections for this item to go into.")),
        Field('name',
              type="string", length=64, required=True,
              notnull=True,
              label ='Name',
              requires = IS_NOT_EMPTY(error_message = "This field cannot be empty. Please type in the item's name."),
              comment = T("Enter a name for the item.")),
        Field('price', type="double", default = 0,
              notnull=True,
              label ='Value',
              requires = IS_FLOAT_IN_RANGE(0, 1e100, error_message = "This field cannot be empty. Please type in the value of the item."),
              comment = T("Enter the items value.")),
        Field('category', type="string", length=32, required=True,
              notnull=True,
              label ='Category',
              requires = IS_IN_DB(db(db.category.name == db.category.name), db.category.id, '%(name)s',
                                  error_message = "This field cannot be empty. Please select the category of your item."),
              comment = T("Choose a category for the item.")),
        Field('quantity', type="integer", default=0,
              notnull=True,
              label ='Owned Quantity',
              requires = IS_INT_IN_RANGE(0, 1e100, error_message = "This field cannot be empty or negative. Please type in the quantity of your item that you want to upload."),
              comment = T("Owned quantity refers to the amount of the item which you have in your possession. If you have at least 1 item, the item will be visible under the 'Owned' tab.")),
        Field('tradable_quantity', type="integer", default=0,
              notnull=True,
              label ='Tradable Quantity',
              requires=IS_INT_IN_RANGE(0, 1e100, error_message = "This field cannot be empty or negative. Please enter the number of this item hat you wish to trade."),
              comment = T("Enter the number of items you wish to trade.")),
        Field('wanted_quantity', type="integer", default=0,
              notnull=True,
              label ='Wanted Quantity',
              requires=IS_INT_IN_RANGE(0, 1e100, error_message = "This field cannot be empty or negative. Please type in how many of this item you want."),
              comment = T("Enter the number of items that you wish to trade for.")),
        Field('description', type="text", length=65536, default="",
              notnull=True,
              label ='Description',
              requires = None,
              comment = T("Enter a short description for the item.")),
        Field('image', type="upload", uploadfield=True, default="static/images/thumbnail.jpg",
              notnull=True,
              label ='Image',
              requires = IS_EMPTY_OR(IS_IMAGE(extensions=('jpeg','png','jpg'), error_message = "Only '.jpeg', 'png' or 'jpg' images are accepted.")),
              comment = T("Upload an image for your item, otherwise a default image will be set. " +
                          "You can edit this image later."))
)

#Trade table defaults/enums
DEFAULT_TRADE_TITLE = "New trade proposal"

STATUS_PREPARE = 0 #IN PREPARATION
STATUS_ACTIVE = 1 #SENDER ABLE TO EDIT
STATUS_OFFERED = 2 #RECEIVER ABLE TO EDIT
STATUS_ACCEPTED = 3
STATUS_REJECTED = 4
STATUS_CANCELLED = 5

#map (status, is_initial_sender) -> badge
status_badge_map = {
                    (STATUS_PREPARE, True): 'default',
                    (STATUS_ACTIVE, True): 'primary',   #received
                    (STATUS_OFFERED, True): 'info',     #offered
                    (STATUS_ACCEPTED, True): 'success',
                    (STATUS_REJECTED, True): 'danger',
                    (STATUS_CANCELLED, True): 'warning',
                    #(STATUS_PREPARE, False): #SHOULD NEVER SEE THIS
                    (STATUS_ACTIVE, False): 'info',     #offered
                    (STATUS_OFFERED, False): 'primary', #received
                    (STATUS_ACCEPTED, False): 'success',
                    (STATUS_REJECTED, False): 'danger',
                    (STATUS_CANCELLED, False): 'warning'}

#map (status, is_initial_sender) -> label 
status_label_map = {
                    (STATUS_PREPARE, True): 'In Preparation',
                    (STATUS_ACTIVE, True): 'Received',   #received
                    (STATUS_OFFERED, True): 'Offered',   #offered
                    (STATUS_ACCEPTED, True): 'Accepted',
                    (STATUS_REJECTED, True): 'Rejected',
                    (STATUS_CANCELLED, True): 'Cancelled',
                    #(STATUS_PREPARE, False): #SHOULD NEVER SEE THIS
                    (STATUS_ACTIVE, False): 'Offered',   #offered
                    (STATUS_OFFERED, False): 'Received', #received
                    (STATUS_ACCEPTED, False): 'Accepted',
                    (STATUS_REJECTED, False): 'Rejected',
                    (STATUS_CANCELLED, False): 'Cancelled'}

#Trade table
#+sender refers to User; who initially proposed the trade
#+receiver refers to User; who the trade was initially sent to
#+title
#+status value from STATUS constants indicating current trade status
#+message
#+time_created timestamp of Trade creation
#+time_modified timestamp of when proposal was last modified
#+finalised_sender whether the Sender has finalised the trade
#+finalised_receiver whether the Receiver has finalised the trade
db.define_table('trade',
        Field('sender', db.auth_user, default=auth.user_id,
              notnull=True, ondelete="CASCADE"),
        Field('receiver', db.auth_user, required=True,
              notnull=True, ondelete="CASCADE"),
        Field('title', type="string", length=64, default=DEFAULT_TRADE_TITLE,
              notnull=True),
        Field('status', type="integer", default=STATUS_PREPARE,
              notnull=True),
        Field('message', type="string", length=512, default="",
              notnull=True),
        Field('time_created', type='datetime', default=datetime.now,
              notnull=True, writable=False),
        Field('time_modified', type='datetime', default=datetime.now, update=datetime.now,
              notnull=True, writable=False),
        Field('finalised_sender', type='boolean', default=False,
              notnull=True),
        Field('finalised_receiver', type='boolean', default=False,
              notnull=True)
)

#Trade_contains_Object table
#+trade refers to Trade
#+object refers to Object
#+quantity the number of the Objects in the Trade
db.define_table('trade_contains_object',
        Field('trade', db.trade, required=True,
              notnull=True, ondelete="CASCADE"),
        Field('object', db.object, required=True,
              notnull=False, ondelete="SET NULL"),
        Field('quantity', type="integer", required=True,
              notnull=False)
)

class IS_STRING_OR(object):
    def __init__(self, other, comparison_string=""):
        self.other = other
        self.comparison_string = comparison_string
        if hasattr(other, 'multiple'):
            self.multiple = other.multiple
        if hasattr(other, 'options'):
            self.options = self._options

    def __call__(self, value):
        if value == self.comparison_string:
            return (value, None)
        if isinstance(self.other, (list, tuple)):
            error = None
            for item in self.other:
                value, error = item(value)
                if error:
                    break
            return value, error
        else:
            return self.other(value)

    def formatter(self, value):
        if hasattr(self.other, 'formatter'):
            return self.other.formatter(value)
        return value
