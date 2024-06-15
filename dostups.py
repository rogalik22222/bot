from telegram.ext import filters
from database import get_user_role
class UserRoleFilter(filters.BaseFilter):
    def __init__(self, roles):
        self.roles = roles
        super().__init__()

    def filter(self, message):
        user_id = message.from_user.id
        user_role = get_user_role(user_id)
        return user_role in self.roles

registered_d = UserRoleFilter(['registered'])
removed_d = UserRoleFilter(['removed'])
sled_d = UserRoleFilter(['sled'])
tech_d = UserRoleFilter(['tech'])
admin_d = UserRoleFilter(['admin'])
developer_d = UserRoleFilter(['developer'])
LVL1 = (['sled'])
LVL2 = (['sled','tech'])
LVL3 = (['sled','tech', 'admin'])
LVL4 = (['sled', 'tech', 'admin', 'developer'])
LVl5 = (['admin'])
LVl6 = (['developer'])
LVL0 = (['EGORKALOX288'])
