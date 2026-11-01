import sqlite3 

## Helpers.py: Used for all helper functions assocaited with the nodes. 

SCHEMA_NOTES: dict[str, dict[str, str]] = {
    ## Used if there is any context on the data that is missing from the variables names or tables names themselves
    "game": {
        "fg3_pct_home": "three-point field goal percentage, home team",
        "fg3_pct_away": "three-point field goal percentage, away team",
    },
}

def run_sql(cursor: sqlite3.Cursor, sql_str:str)  -> tuple:

    ## Runs the query, returns a tuple
    cursor.execute(sql_str)

    rows = cursor.fetchall()
    columns = [col[0] for col in cursor.description]

    return [dict(zip(columns, row)) for row in rows] 

def format_table_ddl(cursor: sqlite3.Cursor, table_name:str,column_notes: dict[str,str] | None = None) -> str:
    ## Build a create table DDL for one tables, for the LLM to easily read. 

    column_notes = column_notes or {} 
    sql_str = f"PRAGMA table_info({table_name})"
    columns = run_sql(cursor=cursor,sql_str = sql_str)  ## Fetches the column name and column information

    pk_columns = [
        ## gets all names of primary key columns
        name for name, pk in
        sorted(((c['name'], c['pk']) for c in columns if c['pk']), key=lambda x: x[1])
    ]

    
    ## Checks if primary key is more than 1 column
    is_composite = len(pk_columns) > 1

    entries = []  # (base_text, comment_or_None), in output order
    for col in columns:
        col_name = col['name']
        col_type = col['type']
        notnull = col['notnull']
        dflt_value = col['dflt_value']
        pk = col['pk']

        base = f"    {col_name} {col_type}"
        if pk and not is_composite:
            base += " PRIMARY KEY"
        entries.append((base, column_notes.get(col_name)))

    if is_composite:
        ## if there are mulitple keys as the primary key, specify at the bottom
        entries.append((f"    PRIMARY KEY ({', '.join(pk_columns)})", None))

    
    last_index = len(entries) - 1
    lines = []
    for i, (base, comment) in enumerate(entries):
        ## Formats the create table sql as following
        ## adds comma in the line if it's not the last variable
        ## Adds comma if it doesn't exist
        line = base
        if i != last_index:
            line += ","
        if comment:
            line += f"  -- {comment}"
        lines.append(line)

    body = "\n".join(lines)
    ## formats return
    return f"CREATE TABLE {table_name} (\n{body}\n);"

def get_full_schema_ddl(cursor: sqlite3.Cursor) -> str:
    ## makes all DDL strings into one string to present to LLM

    ## Gather all table names
    sql_str = "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    table_names = [row['name'] for row in run_sql(cursor=cursor,sql_str = sql_str)]

    ## uses format_table_ddl to get each table, adds schema notes to them as needed
    table_ddls = [
        format_table_ddl(
            cursor, table_name, column_notes=SCHEMA_NOTES.get(table_name, {})
        )
        for table_name in table_names
    ]

    return "\n\n".join(table_ddls)

def get_schema_ddl_for_tables(cursor:sqlite3.Cursor, tables:list):

    ## Turns the list of tables into a string
    num_tables = len(tables)
    table_list = ''
    for i,t in enumerate(tables): 
        tbl_to_add = "\""+t+"\""
        if i+1 != num_tables:
            tbl_to_add = tbl_to_add + ","
        table_list += tbl_to_add

    sql_str = f"SELECT name FROM sqlite_master WHERE type = 'table' AND name in ({table_list}) ORDER BY name"
    table_names = [row['name'] for row in run_sql(cursor=cursor,sql_str = sql_str)]

    ## uses format_table_ddl to get each table, adds schema notes to them as needed
    table_ddls = [
        format_table_ddl(
            cursor, table_name, column_notes=SCHEMA_NOTES.get(table_name, {})
        )
        for table_name in table_names
    ]

    return "\n\n".join(table_ddls)