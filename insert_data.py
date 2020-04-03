import time
from milvus import *
import getopt
import os
import sys
import psycopg2
import time
from functools import reduce
import numpy as np
from milvus import *

SERVER_ADDR = "192.168.1.58"
SERVER_PORT = 19530
VECTOR_DIMENSION = 2048
table_name = sim_table
metric_type=MetricType.JACCARD

PG_HOST = "localhost"
PG_PORT = 5432
PG_USER = "postgres"
PG_PASSWORD = "postgres"
PG_DATABASE = "postgres"
PG_TABLE_NAME = "milvus"

MILVUS = Milvus()

def connect_milvus_server():
    print("connect to milvus")
    status = MILVUS.connect(host=SERVER_ADDR, port=SERVER_PORT, timeout=100)
    handle_status(status=status)
    return status


def connect_postgres_server():
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD,
                                database=PG_DATABASE)
        print("connect the database!")
        return conn
    except:
        print("unable to connect to the database")


def create_pg_table(conn, cur, PG_TABLE_NAME):
    sql = "CREATE TABLE " + PG_TABLE_NAME + " (smiles text, ids bigint);"
    print(sql)
    try:
        cur.execute(sql)
        conn.commit()
        print("create postgres table!")
    except:
        print("can't create postgres table")
        # sys.exit()


def copy_data_to_pg(conn, cur, file_path):
    sql1 = "copy " + PG_TABLE_NAME + " from '" + file_path + "';"
    sql2 = "create index ids on table " + PG_TABLE_NAME + "(ids);"
    print(sql1,sql2)
    try:
        cur.execute(sql1)
        conn.commit()
        cur.execute(sql2)
        conn.commit()
        print("copy data to pg sucessful!")
    except:
        print("faild  copy!")

def smiles_to_vec(smiles):
    mols = Chem.MolFromSmiles(smiles)
    # fp = AllChem.GetMorganFingerprintAsBitVect(mols, 2, VECTOR_DIMENSION)
    fp = Chem.RDKFingerprint(mols, fpSize=VECTOR_DIMENSION)
    hex_fp = DataStructs.BitVectToFPSText(fp)
    # print(hex_fp)
    vec = bytes.fromhex(hex_fp)
    return vec


def feature_extract(filepath):
    feats = []
    smiles = []
    ids = []
    with open(filepath, 'r') as f:
        for line in f:
            parts = line.split()
            try:
                ids.append(parts[1])
                smiles.append(parts[0])
            except :
                print(line)
            try:
                vec = smiles_to_vec(parts[0])
                feats.append(vec)
            except:
                continue
    return feats, smiles, ids



def do_load(file_path):
    vectors, names, ids = feature_extract(file_path)
    connect_milvus_server()
    status, ok = MILVUS.has_collection(table_name)
    if not ok:
        param = {
            'collection_name': table_name,
            'dimension': VECTOR_DIMENSION,
            'index_file_size': 512,  # optional
            'metric_type': metric_type  # optional
        }
    MILVUS.create_collection(param)


    # status, ids = insert_vectors(index_client, table_name, vectors)
    ids_lens = 0
    while ids_lens<len(vectors) :
        try:
            status, ids = MILVUS.insert(collection_name=table_name, records=vectors[ids_lens:ids_lens+100000], ids = ids[ids_lens:ids_lens+100000])
        except:
            status, ids = MILVUS.insert(collection_name=table_name, records=vectors[ids_lens:len(vectors)], ids = ids[ids_lens:len(vectors)])
        ids_lens += 100000
        total_ids += ids
        print("ids:",len(ids))

    conn = connect_postgres_server()
    cur = conn.cursor()
    create_pg_table(conn, cur)
    copy_data_to_pg(conn, cur, file_path)
    cur.close()
    conn.close()


def main(argv):
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "f:h",
            ["help","file="],
        )
        # print(opts)
    except getopt.GetoptError:
        print("Usage:python insert_data.py --file <file_path> ")
        sys.exit(2)

    for opt_name, opt_value in opts:
        if opt_name in ("-f", "--file"):
            file_path = opt_value
            connect_milvus_server()
            do_load(file_path)
        else:
            print("wrong parameter")
            sys.exit(2)

if __name__ == "__main__":
    main(sys.argv[1:])
