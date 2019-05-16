CREATE TABLE public."unclass"
(
    date_ date,
    time_ time,
    missionID text,
    classification text,
    location text,
    sensortype text
);

CREATE TABLE public."secret"
(
    date_ date,
    time_ time,
    missionID text,
    classification text,
    location text,
    sensortype text
);

CREATE TABLE public."topsecret"
(
    date_ date,
    time_ time,
    missionID text,
    classification text,
    location text,
    sensortype text
);
