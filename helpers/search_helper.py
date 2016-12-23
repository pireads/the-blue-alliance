from collections import defaultdict
from google.appengine.api import search

from consts.award_type import AwardType
from consts.event_type import EventType
from database.award_query import TeamAwardsQuery
from database.event_query import TeamEventsQuery


class SearchHelper(object):
    EVENT_LOCATION_INDEX = 'eventLocation'
    TEAM_LOCATION_INDEX = 'teamLocation'
    TEAM_INDEX = 'team'
    TEAM_YEAR_INDEX = 'teamYear'
    TEAM_EVENT_INDEX = 'teamEvent'

    @classmethod
    def update_event_location_index(cls, event):
        if event.normalized_location and event.normalized_location.lat_lng:
            fields = [
                search.NumberField(name='year', value=event.year),
                search.GeoField(name='location', value=search.GeoPoint(
                    event.normalized_location.lat_lng.lat,
                    event.normalized_location.lat_lng.lon))
            ]
            search.Index(name="eventLocation").put(
                search.Document(doc_id=event.key.id(), fields=fields))

    @classmethod
    def remove_event_location_index(cls, event):
        search.Index(name=EVENT_LOCATION_INDEX).delete(event.key.id())

    @classmethod
    def update_team_location_index(cls, team):
        if team.normalized_location and team.normalized_location.lat_lng:
            fields = [
                search.GeoField(name='location', value=search.GeoPoint(
                    team.normalized_location.lat_lng.lat,
                    team.normalized_location.lat_lng.lon))
            ]
            search.Index(name=cls.TEAM_LOCATION_INDEX).put(
                search.Document(doc_id=team.key.id(), fields=fields))

    @classmethod
    def remove_team_location_index(cls, team):
        search.Index(name=TEAM_LOCATION_INDEX).delete(team.key.id())

    @classmethod
    def update_team_year_index(cls, team):
        awards_future = TeamAwardsQuery(team.key.id()).fetch_async()
        events_future = TeamEventsQuery(team.key.id()).fetch_async()

        events_by_year = defaultdict(list)
        for event in events_future.get_result():
            events_by_year[event.year].append(event)

        awards_by_event = defaultdict(list)
        for award in awards_future.get_result():
            awards_by_event[award.event.id()].append(award)

        # General stuff that's the same for indexes
        overall_fields = [
            search.NumberField(name='number', value=team.team_number),
            search.TextField(name='name', value=team.name),
            search.TextField(name='nickname', value=team.nickname)
        ]
        if team.normalized_location and team.normalized_location.lat_lng:
            overall_fields += [
                search.GeoField(name='location', value=search.GeoPoint(
                    team.normalized_location.lat_lng.lat,
                    team.normalized_location.lat_lng.lon))
            ]

        # Construct overall and year specific fields
        overall_award_types_count = defaultdict(int)
        overall_event_award_types_count = defaultdict(int)
        overall_event_types_count = defaultdict(int)
        overall_bb_count = 0
        overall_divwin_count = 0
        overall_cmpwin_count = 0
        for year, events in events_by_year.items():
            year_fields = overall_fields + [search.NumberField(name='year', value=year)]
            year_award_types_count = defaultdict(int)
            year_event_award_types_count = defaultdict(int)
            year_event_types_count = defaultdict(int)
            year_bb_count = 0
            year_divwin_count = 0
            year_cmpwin_count = 0
            for event in events:
                if event.event_type_enum not in EventType.SEASON_EVENT_TYPES:
                    continue

                # Allow searching/sorting by event type
                overall_event_types_count[event.event_type_enum] += 1
                year_event_types_count[event.event_type_enum] += 1

                # One event
                event_fields = year_fields + [search.AtomField(name='event_key', value=event.key.id())]
                award_types_count = defaultdict(int)
                event_award_types_count = defaultdict(int)
                bb_count = 0
                for award in awards_by_event.get(event.key.id(), []):
                    # Allow searching/sorting by award type
                    overall_award_types_count[award.award_type_enum] += 1
                    year_award_types_count[award.award_type_enum] += 1
                    award_types_count[award.award_type_enum] += 1

                    # Allow searching/sorting by award type and event type
                    ea_type = '{}_{}'.format(award.event_type_enum, award.award_type_enum)
                    overall_event_award_types_count[ea_type] += 1
                    year_event_award_types_count[ea_type] += 1
                    event_award_types_count[ea_type] += 1

                    # Allow searching/sorting by blue banners
                    if award.award_type_enum in AwardType.BLUE_BANNER_AWARDS:
                        overall_bb_count += 1
                        year_bb_count += 1
                        bb_count += 1

                    # Allow searching/sorting by div/cmp winner
                    if award.award_type_enum == AwardType.WINNER:
                        if award.event_type_enum == EventType.CMP_DIVISION:
                            overall_divwin_count += 1
                            year_divwin_count += 1
                        elif award.event_type_enum == EventType.CMP_FINALS:
                            overall_cmpwin_count += 1
                            year_cmpwin_count += 1

                event_fields += [
                    search.NumberField(name='bb_count', value=bb_count)] + [
                    search.NumberField(
                        name='award_{}_count'.format(award_type),
                        value=count) for award_type, count in award_types_count.items()] + [
                    search.NumberField(
                        name='event_award_{}_count'.format(event_award_type),
                        value=count) for event_award_type, count in event_award_types_count.items()]

                # Put event index
                search.Index(name=cls.TEAM_EVENT_INDEX).put(
                    search.Document(
                        doc_id='{}_{}'.format(team.key.id(), event.key.id()),
                        fields=event_fields))

            year_fields += [
                search.NumberField(name='bb_count', value=year_bb_count),
                search.NumberField(name='divwin_count', value=year_divwin_count),
                search.NumberField(name='cmpwin_count', value=year_cmpwin_count)] + [
                search.NumberField(
                    name='award_{}_count'.format(award_type),
                    value=count) for award_type, count in year_award_types_count.items()] + [
                search.NumberField(
                    name='event_award_{}_count'.format(event_award_type),
                    value=count) for event_award_type, count in year_event_award_types_count.items()] + [
                search.NumberField(
                    name='event_{}_count'.format(event_type),
                    value=count) for event_type, count in year_event_types_count.items()]

            # Put year index
            search.Index(name=cls.TEAM_YEAR_INDEX).put(
                search.Document(doc_id='{}_{}'.format(team.key.id(), year), fields=year_fields))

        overall_fields += [
            search.NumberField(name='bb_count', value=overall_bb_count),
            search.NumberField(name='divwin_count', value=overall_divwin_count),
            search.NumberField(name='cmpwin_count', value=overall_cmpwin_count)] + [
            search.NumberField(
                name='award_{}_count'.format(award_type),
                value=count) for award_type, count in overall_award_types_count.items()] + [
            search.NumberField(
                name='event_award_{}_count'.format(event_award_type),
                value=count) for event_award_type, count in overall_event_award_types_count.items()] + [
            search.NumberField(
                name='event_{}_count'.format(event_type),
                value=count) for event_type, count in overall_event_types_count.items()]

        # Put overall index
        search.Index(name=cls.TEAM_INDEX).put(
            search.Document(doc_id='{}'.format(team.key.id()), fields=overall_fields))
