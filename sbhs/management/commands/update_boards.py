'''
   This command creates a moderator group and adds users to the moderator group
   with permissions to add, change and delete
   the objects in the exam app.
'''

# django imports
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group, Permission

# local imports
from django.conf import settings
from sbhs.models import Board
from sbhs.views import map_sbhs_to_rpi


class Command(BaseCommand):
    help = 'Ping all boards and update status of boards'

    def handle(self, *args, **options):
        app_label = 'sbhs'
        if settings.SBHS_API_IPS:
            try:
                board_check, dead_servers = map_sbhs_to_rpi()
                board = Board()
                all_mac_ids = []
                for machines in board_check:
                    all_mac_ids.extend(machines["mac_ids"])
                board.switch_off_inactive_boards(all_mac_ids)
                self.stdout.write('Updated Board Status')
                if dead_servers:
                    self.stdout.write('Servers {0} are not responding.'\
                                       .format(", ".join(dead_servers))
                                       )
            except Exception as e:
                self.stdout.write('Failed updating Board because {0}'\
                                  .format(e)
                                  )
        else:
            self.stdout.write('No API IP added in settings.py. '
                "   Please try with adding IPs in the SBHS_API_IPS variable "
                )
