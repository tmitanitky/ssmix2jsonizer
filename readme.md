# SSMIX2JSONizer

SSMIX2(HL7v2.5準拠)形式のメッセージを、その構造を保ってJSON化します。

## Description
SS-MIX2が準拠するHL7v2.5形式では、セグメントに繰り返しが許容されていたり、各フィールドのデータ型も、また違うデータ型の配列によって構成されていたりと、階層的な構造を持っています。これらの情報がHL7v2.5メッセージとして独自の直列化がなされていて、直接利用することは難しいです。本スクリプトでは、各種規約からできるだけ構造を保ってJSON化します。

単純にセグメントをパースするだけではなく、データ種別・メッセージ構造ごとにメッセージ内での各セグメントの繰り返し構造もJSONに表現されるようにしました。また、キーに番号ではなくフィールド名、エレメント名を用いるため、可読性が高いjsonが出力できます。

## Requirements
python >= 3.6.0

## Usage
```
pip install .dist/ssmix2jsonizer-0.0.1.tar.gz
```


```
Jsonizer.jsonize(ssmix2_data_category, ssmix2_message, deidentify=True, nest_prefix='', nest_suffix='_N', 
        is_seq_prefix_in_field_name=True, field_name_lang='en',
        is_seq_prefix_in_element_name=True, element_name_lang='en',
        ssmix2_only=True, encoding='UTF-8'):)
```

SS-MIX2のデータ種別をssmix2_data_category, SS-MIX2メッセージをssmix2_messageに指定します。ssmix2_messageはメッセージファイルのパスでも構いません。

deidentify：Trueで仮名化(β)したjsonを出力します。XPNにおけるFamili Name, Given Nameなど個人情報に関わると思われるエレメントを隠ぺいします。医療従事者側も、IDを残して氏名は隠ぺいする設計です。十分な隠ぺいがなされているか、必ず確認してください。なお、IDENTITY_SEGMENTS, IDENTITY_DATA_TYPES_ELEMENT, IDENTITY_FIELDSを編集することでカスタマイズ可能です。

nest_prefix, nest_suffix：繰り返し構造のあるフィールド名に付与するprefix, suffixです。elasticsearch使用時に使用されることを想定しています。

is_seq_prefix_in_field_name：フィールド名に、「02_PatientID」(PID.2)といったシーケンス番号を付与します。

field_name_lang：'ja'とすれば日本語フィールド名で出力します

is_seq_prefix_in_element_name：エレメント名に、「01_FamilyName」(XPN.1)といったシーケンス番号を付与します。

element_name_lang：'ja'とすれば日本語エレメント名で出力します

ssmix2_only: SS-MIX2ガイドラインにおいて、'N'（使用しない）となっているフィールドがもし含まれていてもスキップします。

encoding: メッセージの文字コードを指定します。SS-MIX2の規定の文字セットは「~ISO IR87」であり、SS-MIX2構築ガイドラインにも「1バイト系文字はISO IR-6(ASCII)、2バイト系文字はISO IR87(JIS漢字コード)」と記載されています。encodingとしては、'iso-2022-jp'が対応します。

## Example
```
from ssmix2jsonizer import Jsonizer

jsonizer = Jsonizer()
jsonizer.jsonize('ADT-01',
'''MSH|^~\&|HIS123|SEND|GW|RCV|20111220224447.3399||ADT^A08^ADT_A01|20111220000001|P|2.5||||||~ISO IR87||
ISO 2022-1994|SS-MIX2_1.20^SS-MIX2^1.2.392.200250.2.1.100.1.2.120^ISO
EVN||201112202100|||||SEND001
PID|0001||9999013||患者^太郎^^^^^L^I~カンジャ^タロウ^^^^^L^P||19480405|M|||^^^^422-8033^JPN^H^静岡県静岡市登呂１－３－５||^PRN^PH^^^^^^^^^054-000-0000~^EMR^PH^^^^^^^^^03-5999-9999|^WPN^PH^^^^^^^^^03-3599-9993|||||||||||||||||||20111219121551
NK1|1|患者^太郎^^^^^L^I~カンジャ^タロウ^^^^^L^P|SEL^本人^HL70063|^^^^422-8033^JPN^H^静岡県静岡市登呂１－３－５~^^^^1050003^^B^東京都港区鹿ノ門６丁目３番３号|^PRN^PH^^^^^^^^^054-000-0000|^WPN^PH^^^^^^^^^03-3599-9993|||||||鹿ノ門商事株式会社^D
PV1|0001|I|32^302^1^^^N||||220^医師^一郎^^^^^^^L^^^^^I
DB1|1|PT||Y
OBX|1|NM|9N001000000000001^身長^JC10||167.8|cm^cm^ISO+|||||F
OBX|2|NM|9N006000000000001^体重^JC10||63.5|kg^kg^ISO+|||||F
OBX|3|CWE|5H010000001999911^血液型-ABO式^JC10||A^A^JSHR002||||||F
OBX|4|CWE|5H020000001999911^血液型-Rh式^JC10||+^Rh+^JSHR002||||||F
AL1|1|DA^薬剤アレルギー^HL70127|1^ペニシリン^99XYZ
IN1|1|67^国民健康保険退職者^JHSD0001|67999991|||||||||20091201|||||SEL^本人^HL70063
''')
```
メッセージ例は構築ガイドラインより引用

## LICENCE
非商用利用に限り、制限なく利用・配布・改変可能。
引用部は引用元のLICENCEに従う。

## References
SS-MIX2 標準化ストレージ 仕様書 Ver.1.2g, 日本医療情報学会

SS-MIX2 標準化ストレージ 構成の説明と構築ガイドライン Ver.1.2g, 日本医療情報学会

12-002_JAHIS放射線データ交換規約Ver.2.3, 保健医療福祉情報システム工業会（JAHIS）

12-004_JAHIS内視鏡データ交換規約Ver.2.1, 保健医療福祉情報システム工業会（JAHIS）

16-004_JAHIS臨床検査データ交換規約Ver.4.0C, 保健医療福祉情報システム工業会（JAHIS）

16-005_JAHIS生理検査データ交換規約Ver.3.0C, 保健医療福祉情報システム工業会（JAHIS）

17-009_JAHIS注射データ交換規約Ver.2.1C, 保健医療福祉情報システム工業会（JAHIS）

18-003_JAHIS病名情報データ交換規約 Ver.3.1C, 保健医療福祉情報システム工業会（JAHIS）

15-002_JAHISデータ交換規約（共通編）Ver.1.2, 保健医療福祉情報システム工業会（JAHIS）

17-005_JAHIS処方データ交換規約Ver.3.0C, 保健医療福祉情報システム工業会（JAHIS）