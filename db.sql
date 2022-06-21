create table settings (
    phone_server TEXT,
    mysql_host TEXT,
    mysql_user TEXT,
    mysql_pass TEXT,
    mysql_db TEXT,
    static_folder TEXT,
    ntp_server TEXT,
    model_misc TEXT
);

create table users (
    username VARCHAR(50),
    password VARCHAR(50),
    permissions INT
);

create table ext_mac_map (
    extension TEXT,
    mac VARCHAR(12),
    template TEXT,
    misc TEXT
);
