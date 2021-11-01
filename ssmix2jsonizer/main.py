import json
#import pandas as pd
import re
import os
import warnings

from pathlib import WindowsPath, PosixPath

DT_PATTERN = re.compile(r'^\d{4}((0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])?)?$')
DTM_PATTERN = re.compile(r'^\d{4}((0[1-9]|1[0-2])((0[1-9]|[12][0-9]|3[01])(([01][0-9]|2[0-4])(([0-5][0-9])(([0-5][0-9])(\.[0-9]{1,4})?)?)?)?)?)?([+-](0[0-9]|1[0-3])[0-5][0-9])?$')
TM_PATTERN = re.compile(r'^(([01][0-9]|2[0-4])(([0-5][0-9])(([0-5][0-9])(\.[0-9]{1,4})?)?)?)?([+-](0[0-9]|1[0-3])[0-5][0-9])?$')

IDENTITY_SEGMENTS=['NK1']

IDENTITY_DATA_TYPES_ELEMENT={'XCN':[*range(1,9),15],
                            'XPN':[*range(0,6)],
                            'XAD':[*range(0,3),7], #XAD.1 - Street Address, XAD.2 - Other Designation, XAD.3 - City, XAD.8 OtherGeographicDesignation
                            'XTN':[0,3,5,6,11,],
                            'DLN':[0], 
                            'SAD':[0,1,2], #SAD - street address
                            'NDL':[*range(0,11)] #NDL - Name with Date and Location
                            }

IDENTITY_FIELDS={
    'PID': [18,19], #PID.18 - Patient Account Number (CX), PID.19 - SSN Number - Patient (ST)
    'DB1': [3],# DB1.3 - Disabled Person Identifier (CX)
    'IN1': [*range(3,42), *range(43,53)], #2: Insurance Plan ID, 42  Insured's Employment Status.
    'ZI1': [*range(3,42), *range(43,53)], #2: Insurance Plan ID, 42  Insured's Employment Status.
}

def DTValidator(dt):
    if bool(re.match(DT_PATTERN, dt)):
        return True
    else:
        warnings.warn(f'{dt} does not match DT pattern (ex)20210805.')
        return False

def DTMValidator(dtm):
    if bool(re.match(DTM_PATTERN, dtm)):
        return True
    else:
        warnings.warn(f'{dtm} does not match DTM pattern (ex)20210805020000.00+0900')
        return False

def TMValidator(tm):
    if bool(re.match(TM_PATTERN, tm)):
        return True
    else:
        warnings.warn(f'{tm} does not match TM pattern (ex)090000.000+0900')
        return False

with open(os.path.join(os.path.abspath(os.path.dirname(__file__)),
        './json/SSMIX2_FIELD_OPTIONS.json'), 'r', encoding='utf-8') as f:
    SSMIX2_FIELD_OPTIONS = json.load(f)

with open(os.path.join(os.path.abspath(os.path.dirname(__file__)),
        './json/DATATYPE_STRUCTURE.json'), 'r', encoding='utf-8') as f:
    DATATYPE_STRUCTURE = json.load(f)

with open(os.path.join(os.path.abspath(os.path.dirname(__file__)),
        './json/SEGMENT_STRUCTURE.json'),'r', encoding='utf-8') as f:
    SEGMENT_STRUCTURE = json.load(f)

PRIMARY_DATA_TYPES = ['', 'DT','DTM','FT','GTS','ID','IS','NM', 'SI','ST','TM','TX']
# ''は各セグメントの０番目のフィールド。「MSH」などのため

class ssmix2MessageJsonizer():
    def __init__(self, deidentify=True, nest_prefix='', nest_suffix='_Nested', 
        is_seq_prefix_in_field_name=True, field_name_lang='en',
        is_seq_prefix_in_element_name=True, element_name_lang='en',
        ssmix2_only=True, ssmix2_data_category=None, encoding='iso-2022-jp'):
        self.deidentify = deidentify

        self.FIELD_SEPARATOR = FIELD_SEPARATOR = '|'
        self.COMPONENT_SEPARATOR = COMPONENT_SEPARATOR = '^'
        self.REREPETITION_SEPARATOR = REPETITION_SEPARATOR = '~'
        self.ESCAPE_CHARACTER = ESCAPE_CHARACTER = '\\'
        self.SUBCOMPONENT_SEPARATOR = SUBCOMPONENT_SEPARATOR = '&'
        
        self.nestPrefix = nest_prefix
        self.nestSuffix = nest_suffix
        #self.fieldNameLang = field_name_lang
        self.fieldNameKey = 'Name'
        if is_seq_prefix_in_field_name:
            self.fieldNameKey += '_seq'
        if field_name_lang in ['en', 'ja']:
            self.fieldNameKey += '_' + field_name_lang
        else:
            warnings.warn(f'"field_name_lang" must be "en" or "ja". {field_name_lang} was given. Converted to "en".')
            self.fieldNameKey += '_en'
        self.elementNameKey = 'Name'
        if is_seq_prefix_in_element_name:
            self.elementNameKey += '_seq'
        if element_name_lang in ['en', 'ja']:
            self.elementNameKey += '_' + element_name_lang
        else:
            warnings.warn(f'"element_name_lang" must be "en" or "ja". {element_name_lang} was given. Converted to "en".')
            self.elementNameKey += '_en'

        self.ssmix2DataCategory = ssmix2_data_category
        self.ssmix2FieldOptions = SSMIX2_FIELD_OPTIONS[self.ssmix2DataCategory]
        self.ssmix2Only = ssmix2_only
        self.encoding = encoding

    def segmentGenerator(self, message):
        if type(message) is str and ('\r' in message or '\n' in message):
            #SSMIX規約上、行末は<CR>
            for segment in message.splitlines():
                yield segment
        elif type(message) in [str, WindowsPath, PosixPath]:
            with open(message, encoding=self.encoding) as f:
                for segment in f:
                    yield segment.rstrip()
        else:
            for segment in message:
                yield segment.rstrip()
        
    def removeEscape(self, txt):
        # /H/や/B/, /Cxxyy/, /Mxxyyzz/といったエスケープ表記には対応していない
        # 閉じないescapeにも警告を発しない
        strings = txt.split(self.ESCAPE_CHARACTER)
        if not len(strings)%2:
            warnings.warn(f'Escapeが閉じていません: "{txt}"')
        for i, string in enumerate(strings):
            if not i%2:
                continue
            if string=='F':
                strings[i]= self.FIELD_SEPARATOR
            elif string=='S':
                strings[i] = self.COMPONENT_SEPARATOR
            elif string=='T':
                strings[i] = self.SUBCOMPONENT_SEPARATOR
            elif string=='R':
                strings[i] = self.REPETITION_SEPARATOR
            elif string=='E':
                strings[i] = self.ESCAPE_CHARACTER
            elif string=='':
                if i < len(strings)-1:
                    strings[i] = self.ESCAPE_CHARACTER
            else:
                strings[i] = ''
        return ''.join(strings)

    def convertPrimaryDataTypeData(self, dataType, data):
        if dataType == 'NM':
            try:
                float(data)
                return data
            except:
                # logger.warning
                return None
        elif dataType == 'DT':
            if DTValidator(data):
                return data
            else:
                return ''  
        elif dataType =='DTM':
            if DTMValidator(data):
                return data
            else:
                return ''
        elif dataType =='TM':
            if TMValidator(data):
                return data
            else:
                return ''
        elif dataType in ['FT','ST','TX','CF']:
            return self.removeEscape(data)
        else:
            return data

    def createNestedFieldName(self,fieldName):
        nestedFieldName = self.nestPrefix + fieldName + self.nestSuffix
        return nestedFieldName
    
    def jsonizeSingleField(self, fieldData, fieldDataType):
        # fieldData should not be empty.
        # return: value or {componentName: object}, or their array
        if fieldDataType in PRIMARY_DATA_TYPES:
            value = self.convertPrimaryDataTypeData(fieldDataType, fieldData)
            return value
        else:
            d = {}
            components = fieldData.split(self.COMPONENT_SEPARATOR)

            for i, component in enumerate(components):
                if not component:
                    continue
                componentDataType = DATATYPE_STRUCTURE[fieldDataType][i]['DataType']
                componentName = DATATYPE_STRUCTURE[fieldDataType][i][self.elementNameKey]
                if self.deidentify:
                    if (fieldDataType in IDENTITY_DATA_TYPES_ELEMENT) and (
                        i in IDENTITY_DATA_TYPES_ELEMENT[fieldDataType]):
                        d[componentName] = '**DEIDENTIFIED**'
                        continue
                if componentDataType in PRIMARY_DATA_TYPES:
                    value = self.convertPrimaryDataTypeData(componentDataType, component)
                    d[componentName] = value
                else:
                    d[componentName] = {}
                    subcomponents = component.split(self.SUBCOMPONENT_SEPARATOR)
                    for j, subcomponent in enumerate(subcomponents):
                        if not subcomponent:
                            continue
                        subcomponentDataType = DATATYPE_STRUCTURE[componentDataType][j]['DataType']
                        subcomponentName = DATATYPE_STRUCTURE[componentDataType][j][self.elementNameKey]
                        if subcomponentDataType in PRIMARY_DATA_TYPES:
                            value = self.convertPrimaryDataTypeData(subcomponentDataType, subcomponent)
                        else:
                            value = subcomponent
                            warnings.warn(f'Subcomponent "{subcomponent}" consists of Complex DataType: "{subcomponentDataType}".')
                        d[componentName][subcomponentName] = value
            return d
   

    def jsonizeField(self, segmentType, segmentSequence, fieldData, fieldDataType):
        # fieldData is not empty.
        if SEGMENT_STRUCTURE[segmentType][segmentSequence]['Repeatability']:
            # self.REPETITION_SEPARATORの有無でも良いかも。それならsegmentType引数が不要。
            multipleFields = [self.jsonizeSingleField(singleFieldData, fieldDataType) 
                    for singleFieldData in fieldData.split(self.REPETITION_SEPARATOR) if singleFieldData]
            return multipleFields
        else:
            return self.jsonizeSingleField(fieldData, fieldDataType)

    def jsonizeSegment(self, segment):
        d = {}
        segmentType = segment[:3]
        if self.deidentify and segmentType in IDENTITY_SEGMENTS:
            d[segmentType] = '**DEIDENTIFIED**'
            return d
        if segmentType == 'MSH':
            self.FIELD_SEPARATOR = segment[3]
            self.COMPONENT_SEPARATOR = segment[4]
            self.REPETITION_SEPARATOR = segment[5]
            self.ESCAPE_CHARACTER = segment[6]
            self.SUBCOMPONENT_SEPARATOR = segment[7]
            fields = ['MSH', self.FIELD_SEPARATOR] + segment.split(self.FIELD_SEPARATOR)[1:]
        else:
            fields = segment.split(self.FIELD_SEPARATOR)

        for seq, field in enumerate(fields[1:],1):
            if segmentType == 'MSH' and seq == 2:
                # ST型だけどエスケープ処理されないので
                fieldName = SEGMENT_STRUCTURE[segmentType][seq][self.fieldNameKey]
                d[fieldName] = field
            elif not field:
                continue
            elif self.ssmix2Only and self.ssmix2FieldOptions[segmentType][seq] == 'N':
                continue
            else:
                # fieldDataType
                if segmentType =='OBX' and seq == 5:
                    fieldDataType = fields[2]
                    if fieldDataType not in ['AD','CWE','CF','CK','CN','CP','CX','DT','ED','FT'
                        'MO','NM','PN','RP','SN','ST','TM','TN','TS','TX','XAD','XCN','XON','XPN','XTN', 'ZRD']:
                        # ZRD型は日本のHL7拡張
                        warnings.warn(f'OBX-2 must be values on HL7 table 0125, but "{fieldDataType}". Whole segment: {segment}')
                        continue
                else:
                    fieldDataType = SEGMENT_STRUCTURE[segmentType][seq]['DataType']
                
                # fieldName
                fieldName = SEGMENT_STRUCTURE[segmentType][seq][self.fieldNameKey]
                if segmentType =='OBX' and seq == 5:
                    fieldName += '_' + fieldDataType
                    # 同じフィールドにNM型、TX型などが混在すると有効なインデックスが作れない
                if SEGMENT_STRUCTURE[segmentType][seq]['Repeatability'] and (
                    fieldDataType not in PRIMARY_DATA_TYPES):
                    fieldName = self.createNestedFieldName(fieldName)

                if self.deidentify:
                    # XAD,XTN,XAD,XPNは他のDataTypeの入れ子となっておらず、Fieldとしてしか登場しない。
                    # LA1 > AD があるが、LA1はSSMIX2は使用せず、そもそもRXEの「配布先」なので問題ない
                    if segmentType in IDENTITY_FIELDS and seq in IDENTITY_FIELDS[segmentType]:
                        d[fieldName] = '**DEIDENTIFIED**'
                        continue
                
                d[fieldName] = self.jsonizeField(segmentType, seq, field, fieldDataType)
        return d

class ADTMessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='ADT':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='ADT'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['EVN','PID','PV1','PV2']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['NK1','DB1','OBX','AL1','IN1',]:
                d.setdefault(self.createNestedFieldName(segmentType),[]).append(self.jsonizeSegment(segment))
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class ADT00MessageJsonizer(ADTMessageJsonizer):pass
class ADT01MessageJsonizer(ADTMessageJsonizer):pass
class ADT12MessageJsonizer(ADTMessageJsonizer):pass
class ADT21MessageJsonizer(ADTMessageJsonizer):pass
class ADT22MessageJsonizer(ADTMessageJsonizer):pass
class ADT31MessageJsonizer(ADTMessageJsonizer):pass
class ADT32MessageJsonizer(ADTMessageJsonizer):pass
class ADT41MessageJsonizer(ADTMessageJsonizer):pass
class ADT42MessageJsonizer(ADTMessageJsonizer):pass
class ADT51MessageJsonizer(ADTMessageJsonizer):pass
class ADT52MessageJsonizer(ADTMessageJsonizer):pass

class ADT61MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='ADT-61':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='ADT-61'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['EVN','PID','PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['IAM',]:
                d.setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class PPR01MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='PPR-01':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='PPR-01'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType == 'PRB':
                d.setdefault(self.createNestedFieldName('PROBLEM'),[]).append({
                    segmentType: self.jsonizeSegment(segment)
                })
            elif segmentType =='ZPR':
                d[self.createNestedFieldName('PROBLEM')][-1][segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['ZPD','ZI1','ORC']:
                d[self.createNestedFieldName('PROBLEM')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class OMDMessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMD':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMD'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['AL1',]:
                d.setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append({
                    segmentType: self.jsonizeSegment(segment)
                })
            elif segmentType in ['TQ1','ODS']:
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class OMP01MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMP-01':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMP-01'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['AL1',]:
                d.setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append({
                    segmentType: self.jsonizeSegment(segment)
                })
            elif segmentType in ['TQ1','RXE']:
                # TQ1: 「[SS-MIX2] ORC、RXE に対して常に１件しか使用しない。」
                d[self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['RXR']:
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class OMP11MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMP-11':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMP-11'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['AL1',]:
                d.setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append({
                    segmentType: self.jsonizeSegment(segment)
                })
            elif segmentType in ['TQ1','RXE']:
                # TQ1: 「[SS-MIX2] ORC、RXE に対して常に１件しか使用しない。」
                d[self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
            elif segmentType == 'RXR':
                if self.createNestedFieldName('ADMINISTRATION') in d[self.createNestedFieldName('ORDER')][-1]:
                    d[self.createNestedFieldName('ORDER')][-1][self.createNestedFieldName('ADMINISTRATION')][-1][segmentType] = self.jsonizeSegment(segment)
                else:
                    d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                        self.jsonizeSegment(segment)
                    )
            elif segmentType == 'RXA':
                # nest内の初の要素が繰り返し
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName('ADMINISTRATION'),[{}]
                    )[-1].setdefault(self.createNestedFieldName(segmentType), []).append(
                        self.jsonizeSegment(segment)
                    )
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d


class OMP02MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMP-02':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMP-02'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['AL1',]:
                d.setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append({
                    segmentType: self.jsonizeSegment(segment)
                })
            elif segmentType in ['TQ1','RXE']:
                # TQ1: 「[SS-MIX2] ORC、RXE に対して常に１件しか使用しない。」
                d[self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['RXR','RXC','OBX','CTI']:
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class OMP12MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMP-12':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMP-12'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['AL1',]:
                d.setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append({
                    segmentType: self.jsonizeSegment(segment)
                })
            elif segmentType in ['TQ1','RXE']:
                # TQ1: 「[SS-MIX2] ORC、RXE に対して常に１件しか使用しない。」
                d[self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['RXC']:
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType == 'RXR':
                if self.createNestedFieldName('ADMINISTRATION') in d[self.createNestedFieldName('ORDER')][-1]:
                    d[self.createNestedFieldName('ORDER')][-1][self.createNestedFieldName('ADMINISTRATION')][-1][segmentType] = self.jsonizeSegment(segment)
                else:
                    d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                        self.jsonizeSegment(segment)
                    )
            elif segmentType == 'RXA':
                # nest内の初の要素が繰り返し
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName('ADMINISTRATION'),[{}]
                    )[-1].setdefault(self.createNestedFieldName(segmentType), []).append(
                        self.jsonizeSegment(segment)
                    )
            elif segmentType =='OBX':
                d[self.createNestedFieldName('ORDER')][-1][self.createNestedFieldName('ADMINISTRATION')][-1].setdefault(
                    self.createNestedFieldName(segmentType),[]
                ).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType =='CTI':
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType), []).append(
                    self.jsonizeSegment(segment)
                )
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class OML01MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OML-01':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OML-01'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['AL1',]:
                d.setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType == 'SPM':
                d.setdefault(self.createNestedFieldName('SPECIMEN'),[]).append(
                    {segmentType:self.jsonizeSegment(segment)}
                )
            elif segmentType =='ORC':
                d[self.createNestedFieldName('SPECIMEN')][-1].setdefault(self.createNestedFieldName('ORDER'),[{}]
                    )[-1][segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['TQ1', 'OBR']:
                d[self.createNestedFieldName('SPECIMEN')][-1][self.createNestedFieldName('ORDER')][-1][segmentType]=self.jsonizeSegment(segment)
            elif segmentType == 'OBX':
                d[self.createNestedFieldName('SPECIMEN')][-1][self.createNestedFieldName('ORDER')][-1].setdefault(
                    self.createNestedFieldName(segmentType), []
                ).append(self.jsonizeSegment(segment))
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class OML11MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OML-11':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OML-11'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType == 'SPM':
                d.setdefault(self.createNestedFieldName('SPECIMEN'),[]).append(
                    {segmentType:self.jsonizeSegment(segment)}
                )
            elif segmentType =='OBR':
                d[self.createNestedFieldName('SPECIMEN')][-1].setdefault(self.createNestedFieldName('ORDER'),[{}]
                    )[-1][self.createNestedFieldName(segmentType)]=self.jsonizeSegment(segment)            
            elif segmentType =='ORC':
                d[self.createNestedFieldName('SPECIMEN')][-1][self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
            elif segmentType == 'OBX':
                d[self.createNestedFieldName('SPECIMEN')][-1][self.createNestedFieldName('ORDER')][-1].setdefault(
                    self.createNestedFieldName(segmentType), []
                ).append(self.jsonizeSegment(segment))
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class OMG01MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMG-01':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMG-01'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append(
                    {segmentType:self.jsonizeSegment(segment)}
                )
            elif segmentType in ['TQ1','OBX']:
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType =='OBR':
                d[self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d


class OMG11MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMG-11':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMG-11'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append(
                    {segmentType:self.jsonizeSegment(segment)}
                )
            elif segmentType in ['OBX','ZE1','IPC']:
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType in ['TQ1','OBR']:
                d[self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
            elif segmentType == 'ZE2':
                d[self.createNestedFieldName('ORDER')][-1][self.createNestedFieldName('ZE1')][-1].setdefault(
                    self.createNestedFieldName(segmentType),[]
                ).append(self.jsonizeSegment(segment))
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class OMG02MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMG-02':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMG-02'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append(
                    {segmentType:self.jsonizeSegment(segment)}
                )
            elif segmentType in ['TQ1','OBX']:
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType =='OBR':
                d[self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d


class OMG12MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMG-12':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMG-12'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append(
                    {segmentType:self.jsonizeSegment(segment)}
                )
            elif segmentType in ['TQ1','OBX','ZE1','IPC']:
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType in ['OBR']:
                if segmentType not in d[self.createNestedFieldName('ORDER')][-1]:
                    d[self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
                else:
                    d[self.createNestedFieldName('ORDER')][-1][self.createNestedFieldName('ZE1')][-1].setdefault(
                        self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d


class OMG03MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMG-03':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMG-03'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['AL1',]:
                d.setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append(
                    {segmentType:self.jsonizeSegment(segment)}
                )
            elif segmentType in ['TQ1','OBX']:
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType =='OBR':
                d[self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class OMG13MessageJsonizer(ssmix2MessageJsonizer):
    def __init__(self, **kwargs):
        if 'ssmix2_data_category' in kwargs and kwargs['ssmix2_data_category']!='OMG-13':
            warnings.warn(f'ssmix2_data_categoryパラメータ：{kwargs["ssmix2_data_category"]}は無視されます。')
        kwargs['ssmix2_data_category']='OMG-13'
        super().__init__(**kwargs)

    def jsonize(self, message):
        d = {}
        gen = self.segmentGenerator(message)
        for segment in gen:
            segmentType = segment[:3]
            if segmentType == 'MSH':
                #FIELD_SEPARATOR = segment[3]
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType in ['PID', 'PV1']:
                d[segmentType] = self.jsonizeSegment(segment)
            elif segmentType == 'ORC':
                d.setdefault(self.createNestedFieldName('ORDER'),[]).append(
                    {segmentType:self.jsonizeSegment(segment)}
                )
            elif segmentType in ['TQ1','OBX']:
                d[self.createNestedFieldName('ORDER')][-1].setdefault(self.createNestedFieldName(segmentType),[]).append(
                    self.jsonizeSegment(segment)
                )
            elif segmentType in ['OBR']:
                if self.createNestedFieldName('ORDER') not in d or (segmentType in d[self.createNestedFieldName('ORDER')][-1]):
                    # 直前のORCが省略されていて、ORDERブロックを開始し、要素を開始する時
                    # ORDERブロックは存在するものの、直前のORCが省略されていて、ORDERブロックの要素を開始する時
                    d.setdefault(self.createNestedFieldName('ORDER'),[]).append(
                    {segmentType:self.jsonizeSegment(segment)}
                    )
                else:
                    d[self.createNestedFieldName('ORDER')][-1][segmentType] = self.jsonizeSegment(segment)
            else:
                warnings.warn(f'Undefined segment type: {segmentType} in {self.ssmix2DataCategory}. Message: {message}')
        return d

class Jsonizer():
    def __init__(self, **kwargs):
        self.adtMessageJsonizer = ADTMessageJsonizer(**kwargs)
        self.jsonizerDict = {
            'ADT-00': self.adtMessageJsonizer,
            'ADT-01': self.adtMessageJsonizer,
            'ADT-12': self.adtMessageJsonizer,
            'ADT-21': self.adtMessageJsonizer,
            'ADT-22': self.adtMessageJsonizer,
            'ADT-31': self.adtMessageJsonizer,
            'ADT-32': self.adtMessageJsonizer,
            'ADT-41': self.adtMessageJsonizer,
            'ADT-42': self.adtMessageJsonizer,
            'ADT-51': self.adtMessageJsonizer,
            'ADT-52': self.adtMessageJsonizer,
            'ADT-61': ADT61MessageJsonizer(**kwargs),
            'PPR-01': PPR01MessageJsonizer(**kwargs),
            'OMD': OMDMessageJsonizer(**kwargs),
            'OMP-01': OMP01MessageJsonizer(**kwargs),
            'OMP-11': OMP11MessageJsonizer(**kwargs),
            'OMP-02': OMP02MessageJsonizer(**kwargs),
            'OMP-12': OMP12MessageJsonizer(**kwargs),
            'OML-01': OML01MessageJsonizer(**kwargs),
            'OML-11': OML11MessageJsonizer(**kwargs),
            'OMG-01': OMG01MessageJsonizer(**kwargs),
            'OMG-11': OMG11MessageJsonizer(**kwargs),
            'OMG-02': OMG02MessageJsonizer(**kwargs),
            'OMG-12': OMG12MessageJsonizer(**kwargs),
            'OMG-03': OMG03MessageJsonizer(**kwargs),
            'OMG-13': OMG13MessageJsonizer(**kwargs)
            }
    
    def jsonize(self, dataCategory, message):
        return self.jsonizerDict[dataCategory].jsonize(message)
