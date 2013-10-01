from io import FileIO
from os import fstat

from cfb.constants import ENDOFCHAIN
from cfb.directory import Directory
from cfb.directory.entry import RootEntry
from cfb.exceptions import MaybeDefected, ErrorDefect
from cfb.header import Header
from cfb.helpers import ByteHelpers, cached

__all__ = ["CfbIO"]


class CfbIO(FileIO, MaybeDefected, ByteHelpers):
    def __init__(self, name, raise_if=ErrorDefect):
        super(CfbIO, self).__init__(name, mode='rb')
        MaybeDefected.__init__(self, raise_if=raise_if)

        self.length = fstat(self.fileno()).st_size
        self.header = Header(self)

        self.directory = Directory(self)
        self.directory.read()

    @cached
    def root(self):
        sector = self.header.directory_sector_start
        position = (sector + 1) << self.header.sector_shift
        return RootEntry(self, position)

    def next_fat(self, current):
        sector_size = self.header.sector_size / 4
        block = current / sector_size
        difat_position = 76

        if block >= 109:
            block -= 109
            sector = self.header.difat_sector_start

            while block >= sector_size:
                position = (sector + 1) << self.header.sector_shift
                position += self.header.sector_size - 4
                sector = self.read_long(position)
                block -= sector_size - 1

            difat_position = (sector + 1) << self.header.sector_shift
        fat_sector = self.read_long(difat_position + block * 4)

        fat_position = (fat_sector + 1) << self.header.sector_shift
        fat_position += (current % sector_size) * 4

        return self.read_long(fat_position)

    def next_minifat(self, current):
        position = 0
        sector_size = self.header.sector_size / 4
        sector = self.header.minifat_sector_start

        while sector != ENDOFCHAIN and (current + 1) * sector_size <= current:
            sector = self.next_fat(sector)
            position += 1

        if sector == ENDOFCHAIN:
            return ENDOFCHAIN

        minifat_position = (sector + 1) << self.header.sector_shift
        minifat_position += (current - position * sector_size) * 4

        return self.read_long(minifat_position)

    def __getitem__(self, item):
        if isinstance(item, basestring):
            return self.directory.by_name(item)
        return self.directory[item]