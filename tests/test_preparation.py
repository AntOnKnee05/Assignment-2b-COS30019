"""Small synthetic workbook tests plus plotted-series selection checks."""
import csv
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import xlrd
from traffic.prepare import convert, observations, site_id, FIELDS
from traffic.plot_day import load_day


class Sheet:
    def __init__(self):
        self.rows = [[0,0,0,0] + [i/96 for i in range(96)],
                     ['SCATS Number','Location','VR Internal Loc','Date'] + [f'V{i:02}' for i in range(96)],
                     ['0970','ROAD',1,38991.010416666664] + [86,83,52,58] + [0]*92]
    @property
    def nrows(self): return len(self.rows)
    def row_values(self, row): return self.rows[row]
    def cell_value(self, row, col): return self.rows[row][col]
    def cell_type(self, row, col):
        if row>=2 and col==3: return xlrd.XL_CELL_DATE
        value=self.cell_value(row,col)
        return xlrd.XL_CELL_EMPTY if value=='' else (xlrd.XL_CELL_NUMBER if isinstance(value,(int,float)) else xlrd.XL_CELL_TEXT)


def read(sheet):
    stats=dict(source_rows=0,output_rows=0,missing_measurements=0,observed_measurements=0,sum_vehicle_counts=0)
    return list(observations(sheet,0,stats)),stats


class PreparationTests(unittest.TestCase):
    def test_counts_times_and_date(self):
        records,stats=read(Sheet())
        self.assertEqual(len(records),96)
        self.assertEqual(records[0],['0970','ROAD',1,'2006-10-01','00:00',86])
        self.assertEqual(records[-1][-2],'23:45')
        self.assertEqual(stats['sum_vehicle_counts'],279)
    def test_leading_zero_id(self):
        self.assertEqual(site_id(970.0),'0970')
        self.assertEqual(site_id('0970'),'0970')
    def test_separate_internal_locations(self):
        sheet=Sheet(); other=sheet.rows[2].copy();other[2]=6;sheet.rows.append(other)
        records,stats=read(sheet)
        self.assertEqual(len(records),192)
        self.assertEqual(stats['series'],2)
    def test_duplicate_is_error(self):
        sheet=Sheet();sheet.rows.append(sheet.rows[2].copy())
        with self.assertRaisesRegex(ValueError,'Duplicate'):read(sheet)
    def test_missing_is_not_zero(self):
        sheet=Sheet();sheet.rows[2][4]=''
        records,stats=read(sheet)
        self.assertEqual(records[0][-1],'')
        self.assertEqual(records[4][-1],0)
        self.assertEqual(stats['missing_measurements'],1)
    def test_bad_counts_rejected(self):
        for value in [-1,2.5,float('nan'),float('inf'),'invalid']:
            with self.subTest(value=value):
                sheet=Sheet();sheet.rows[2][4]=value
                with self.assertRaises(ValueError):read(sheet)
    def test_bad_interval_header(self):
        sheet=Sheet();sheet.rows[0][4]=.5
        with self.assertRaisesRegex(ValueError,'interval'):read(sheet)
    def test_failed_conversion_preserves_existing_output(self):
        sheet=Sheet();sheet.rows[2][4]=-1
        class Book:
            datemode=0
            def sheet_by_name(self,name):return sheet
            def release_resources(self):pass
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'data.csv';output.write_text('existing')
            with patch('traffic.prepare.xlrd.open_workbook',return_value=Book()):
                with self.assertRaises(ValueError):convert(Path(directory)/'input.xls',output)
            self.assertEqual(output.read_text(),'existing')
            self.assertEqual(len(list(Path(directory).iterdir())),1)
    def test_plot_missing_slots_and_unknown_series(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'data.csv'
            with output.open('w',newline='') as handle:
                writer=csv.writer(handle);writer.writerow(FIELDS)
                writer.writerow(['0970','ROAD',1,'2006-10-01','00:00',86])
                writer.writerow(['0970','OTHER',6,'2006-10-01','00:00',99])
            label,values=load_day(output,'0970',1,'2006-10-01')
            self.assertEqual(label,'ROAD');self.assertEqual(values[0],86)
            self.assertTrue(math.isnan(values[1]))
            with self.assertRaisesRegex(ValueError,'No records'):
                load_day(output,'0970',2,'2006-10-01')

if __name__=='__main__':unittest.main()
