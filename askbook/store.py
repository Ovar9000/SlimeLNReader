"""Weaviate store: connection, the three spec collections, typed helpers."""
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.query import Filter, MetadataQuery, Sort

from .config import WEAVIATE_HOST, WEAVIATE_HTTP_PORT, WEAVIATE_GRPC_PORT


def connect():
    client = weaviate.connect_to_local(
        host=WEAVIATE_HOST, port=WEAVIATE_HTTP_PORT, grpc_port=WEAVIATE_GRPC_PORT
    )
    if not client.is_ready():
        raise RuntimeError("Weaviate not ready")
    return client


def ensure_schema(client, reset=False):
    """Create NovelChunk / WikiChunk / CharacterStateLog (vectorizer: none)."""
    specs = {
        "NovelChunk": [
            Property(name="text", data_type=DataType.TEXT),
            Property(name="volume", data_type=DataType.INT, index_filterable=True),
            Property(name="chapter", data_type=DataType.TEXT, index_filterable=True),
            Property(name="page_start", data_type=DataType.INT),
            Property(name="page_end", data_type=DataType.INT),
            Property(name="global_position", data_type=DataType.INT, index_filterable=True),
            Property(name="section_label", data_type=DataType.TEXT, index_filterable=True),
            Property(name="arc_name", data_type=DataType.TEXT, index_filterable=True),
            Property(name="characters_mentioned", data_type=DataType.TEXT_ARRAY, index_filterable=True),
            Property(name="is_ground_truth", data_type=DataType.BOOL, index_filterable=True),
        ],
        "WikiChunk": [
            Property(name="text", data_type=DataType.TEXT),
            Property(name="source_url", data_type=DataType.TEXT),
            Property(name="content_type", data_type=DataType.TEXT, index_filterable=True),
            Property(name="global_position_estimate", data_type=DataType.INT, index_filterable=True),
            Property(name="confidence", data_type=DataType.TEXT, index_filterable=True),
            Property(name="characters_mentioned", data_type=DataType.TEXT_ARRAY, index_filterable=True),
            Property(name="is_ground_truth", data_type=DataType.BOOL, index_filterable=True),
        ],
        "CharacterStateLog": [
            Property(name="character_canonical_name", data_type=DataType.TEXT, index_filterable=True),
            Property(name="character_aliases", data_type=DataType.TEXT_ARRAY, index_filterable=True),
            Property(name="stat_type", data_type=DataType.TEXT, index_filterable=True),
            Property(name="value_text", data_type=DataType.TEXT),
            Property(name="global_position", data_type=DataType.INT, index_filterable=True),
            Property(name="volume", data_type=DataType.INT),
            Property(name="chapter", data_type=DataType.TEXT),
            Property(name="page", data_type=DataType.INT),
            Property(name="source_type", data_type=DataType.TEXT, index_filterable=True),
            Property(name="confidence", data_type=DataType.TEXT, index_filterable=True),
        ],
    }
    for name, props in specs.items():
        if client.collections.exists(name):
            if reset:
                client.collections.delete(name)
            else:
                continue
        client.collections.create(
            name=name,
            description=f"Ask-the-Book collection: {name}",
            vector_config=Configure.Vectors.self_provided(),
            properties=props,
        )
    return list(specs)


def pos_filter(prop, pos):
    """Spoiler guard: only content at or before the reader's position."""
    return Filter.by_property(prop).less_or_equal(pos)


def search_chunks_vec(client, collection, query_vector, reader_pos, pos_prop,
                      limit=5, extra_filter=None):
    """Vector search with hard position cutoff. Never returns future content."""
    filt = pos_filter(pos_prop, reader_pos)
    if extra_filter is not None:
        filt = filt & extra_filter
    col = client.collections.get(collection)
    res = col.query.near_vector(
        near_vector=query_vector,
        limit=limit,
        filters=filt,
        return_metadata=MetadataQuery(distance=True),
    )
    return [o.properties for o in res.objects]


def search_chunks(client, collection, query_vector, reader_pos, pos_prop,
                  limit=5, extra_filter=None):
    return search_chunks_vec(client, collection, query_vector, reader_pos,
                             pos_prop, limit=limit, extra_filter=extra_filter)


def latest_state(client, character, stat_type, reader_pos):
    """Structured lookup: most recent row for character+stat at/before position."""
    col = client.collections.get("CharacterStateLog")
    filt = (
        Filter.by_property("character_canonical_name").equal(character)
        & Filter.by_property("stat_type").equal(stat_type)
        & Filter.by_property("global_position").less_or_equal(reader_pos)
    )
    res = col.query.fetch_objects(
        filters=filt,
        sort=Sort.by_property("global_position", ascending=False),
        limit=1,
    )
    objs = res.objects
    return objs[0].properties if objs else None


def count(client, collection):
    col = client.collections.get(collection)
    return col.aggregate.over_all(total_count=True).total_count
